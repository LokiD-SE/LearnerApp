import type { PGlite, Transaction } from '@electric-sql/pglite';

/**
 * Exercise: make SandPay's refund correct under concurrency and failure.
 *
 * `refund(db, paymentId, amountMinor, reason)` must:
 *
 * 1. Return `{ ok: false, reason: 'invalid_amount' }` for an amount that is not a positive
 *    integer - without touching the database.
 * 2. Do all of its writes in ONE transaction (`db.transaction(async (tx) => ...)`), so they
 *    happen together or not at all:
 *      - add the amount to `payments.refunded_minor`,
 *      - insert the `refunds` row,
 *      - insert an `outbox` row: event_type 'refund.created', payload
 *        { refundId, paymentId, amountMinor, currency }.
 * 3. Never refund more than was captured, even when two refunds for the same payment run at
 *    the same time. Do the check and the change in ONE conditional UPDATE
 *    (`... WHERE id = $1 AND refunded_minor + $2 <= captured_minor RETURNING ...`) - not a
 *    SELECT followed by an UPDATE.
 * 4. When that UPDATE changes no row, find out why (inside the same transaction) and return
 *    `{ ok: false, reason: 'not_found' }` or
 *    `{ ok: false, reason: 'exceeds_refundable', refundableMinor }`.
 * 5. On success return `{ ok: true, refundId, refundedMinor }` (the new running total).
 * 6. Call `hooks.afterRefundRow?.(tx)` right after inserting the refund row. Tests use it to
 *    make the transaction fail half-way; the error must propagate and leave no trace.
 * 7. Use parameters ($1, $2...) for every value - never build SQL from strings.
 *
 * The code below is the "obvious" version. Run the tests and read what breaks.
 */

export type RefundResult =
  | { ok: true; refundId: number; refundedMinor: number }
  | { ok: false; reason: 'invalid_amount' | 'not_found' }
  | { ok: false; reason: 'exceeds_refundable'; refundableMinor: number };

export interface RefundHooks {
  afterRefundRow?: (tx: Transaction) => Promise<void>;
}

interface PaymentRow {
  currency: string;
  captured_minor: number;
  refunded_minor: number;
}

export async function refund(
  db: PGlite,
  paymentId: string,
  amountMinor: number,
  reason: string,
  hooks: RefundHooks = {},
): Promise<RefundResult> {
  const found = await db.query<PaymentRow>(
    'SELECT currency, captured_minor, refunded_minor FROM payments WHERE id = $1',
    [paymentId],
  );
  const payment = found.rows[0];
  if (!payment) return { ok: false, reason: 'not_found' };

  const refundableMinor = payment.captured_minor - payment.refunded_minor;
  if (amountMinor > refundableMinor) return { ok: false, reason: 'exceeds_refundable', refundableMinor };

  const refundedMinor = payment.refunded_minor + amountMinor;
  await db.query('UPDATE payments SET refunded_minor = $2 WHERE id = $1', [paymentId, refundedMinor]);
  const inserted = await db.query<{ id: number }>(
    'INSERT INTO refunds (payment_id, amount_minor, reason) VALUES ($1, $2, $3) RETURNING id',
    [paymentId, amountMinor, reason],
  );
  const refundId = inserted.rows[0]!.id;
  await hooks.afterRefundRow?.(db as unknown as Transaction);
  await db.query('INSERT INTO outbox (event_type, payload) VALUES ($1, $2)', [
    'refund.created',
    JSON.stringify({ refundId, paymentId, amountMinor, currency: payment.currency }),
  ]);
  return { ok: true, refundId, refundedMinor };
}
