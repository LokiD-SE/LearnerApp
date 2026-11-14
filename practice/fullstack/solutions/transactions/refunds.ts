import type { PGlite, Transaction } from '@electric-sql/pglite';

/**
 * Reference solution: SandPay's refund, correct under concurrency and failure.
 * See the exercise file for the contract.
 */

export type RefundResult =
  | { ok: true; refundId: number; refundedMinor: number }
  | { ok: false; reason: 'invalid_amount' | 'not_found' }
  | { ok: false; reason: 'exceeds_refundable'; refundableMinor: number };

export interface RefundHooks {
  afterRefundRow?: (tx: Transaction) => Promise<void>;
}

export async function refund(
  db: PGlite,
  paymentId: string,
  amountMinor: number,
  reason: string,
  hooks: RefundHooks = {},
): Promise<RefundResult> {
  if (!Number.isSafeInteger(amountMinor) || amountMinor <= 0) return { ok: false, reason: 'invalid_amount' };

  return db.transaction(async (tx): Promise<RefundResult> => {
    // Check and change in one statement: the row lock taken by UPDATE makes a concurrent refund
    // wait, and PostgreSQL re-evaluates the WHERE clause on the row it then sees.
    const updated = await tx.query<{ refunded_minor: number; currency: string }>(
      `UPDATE payments
          SET refunded_minor = refunded_minor + $2
        WHERE id = $1 AND refunded_minor + $2 <= captured_minor
    RETURNING refunded_minor, currency`,
      [paymentId, amountMinor],
    );
    const payment = updated.rows[0];
    if (!payment) {
      const current = await tx.query<{ captured_minor: number; refunded_minor: number }>(
        'SELECT captured_minor, refunded_minor FROM payments WHERE id = $1',
        [paymentId],
      );
      const row = current.rows[0];
      if (!row) return { ok: false, reason: 'not_found' };
      return {
        ok: false,
        reason: 'exceeds_refundable',
        refundableMinor: row.captured_minor - row.refunded_minor,
      };
    }

    const inserted = await tx.query<{ id: number }>(
      'INSERT INTO refunds (payment_id, amount_minor, reason) VALUES ($1, $2, $3) RETURNING id',
      [paymentId, amountMinor, reason],
    );
    const refundId = inserted.rows[0]!.id;
    await hooks.afterRefundRow?.(tx);

    // Outbox row in the same transaction: the event exists if and only if the refund does.
    await tx.query('INSERT INTO outbox (event_type, payload) VALUES ($1, $2)', [
      'refund.created',
      JSON.stringify({ refundId, paymentId, amountMinor, currency: payment.currency }),
    ]);
    return { ok: true, refundId, refundedMinor: payment.refunded_minor };
  });
}
