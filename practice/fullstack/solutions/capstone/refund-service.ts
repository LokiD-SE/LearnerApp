// Reference solution: an idempotent refund in one PostgreSQL transaction.
// See the exercise file for the contract.
import { createHash } from 'node:crypto';
import type { PGlite, Transaction } from '@electric-sql/pglite';

export const PROBLEMS = 'https://api.sandpay.example/problems/';

export interface RefundCommand {
  merchantId: number;
  paymentId: string;
  amountMinor: number;
  idempotencyKey: string;
}

export interface ServiceResponse {
  status: number;
  body: Record<string, unknown>;
  replayed: boolean;
}

export interface RefundHooks {
  /** Called inside the transaction after the refund row is written - tests use it to simulate a crash. */
  afterRefund?: (tx: Transaction) => Promise<void>;
}

/** The request's fingerprint: a hash of a canonical form of what the client asked for. */
export function fingerprintOf(command: Pick<RefundCommand, 'paymentId' | 'amountMinor'>): string {
  const canonical = JSON.stringify({ paymentId: command.paymentId, amountMinor: command.amountMinor });
  return createHash('sha256').update(canonical).digest('hex');
}

export async function createRefund(
  db: PGlite,
  command: RefundCommand,
  hooks: RefundHooks = {},
): Promise<ServiceResponse> {
  const { merchantId, idempotencyKey } = command;
  const fingerprint = fingerprintOf(command);

  return db.transaction(async (tx): Promise<ServiceResponse> => {
    // 1. Reserve the key. The primary key makes this atomic: of two requests with the same key, one
    //    inserts and the other inserts nothing (on a real server it waits until the first commits).
    const reserved = await tx.query(
      `INSERT INTO idempotency_keys (merchant_id, key, fingerprint) VALUES ($1, $2, $3)
       ON CONFLICT (merchant_id, key) DO NOTHING RETURNING key`,
      [merchantId, idempotencyKey, fingerprint],
    );

    if (reserved.rows.length === 0) {
      const existing = await tx.query<{
        fingerprint: string;
        status_code: number | null;
        response: Record<string, unknown> | null;
      }>(
        'SELECT fingerprint, status_code, response FROM idempotency_keys WHERE merchant_id = $1 AND key = $2',
        [merchantId, idempotencyKey],
      );
      const row = existing.rows[0]!;
      if (row.fingerprint !== fingerprint) {
        return problem(422, 'idempotency-key-reused', 'Idempotency key reused', {
          detail: 'This Idempotency-Key was already used for a different request.',
        });
      }
      if (row.status_code === null || row.response === null) {
        return problem(409, 'request-in-progress', 'A request with this key is still being processed');
      }
      return { status: row.status_code, body: row.response, replayed: true };
    }

    // 2. Do the work. Check and change in one statement, scoped to the merchant: the row lock makes a
    //    concurrent refund of the same payment wait, and the WHERE clause is re-checked afterwards.
    const outcome = await refundPayment(tx, command, hooks);

    // 3. Store the outcome with the key, in the same transaction: the key and the refund are committed
    //    together or not at all, so a crash before COMMIT leaves the key free for the retry.
    await tx.query(
      'UPDATE idempotency_keys SET status_code = $3, response = $4 WHERE merchant_id = $1 AND key = $2',
      [merchantId, idempotencyKey, outcome.status, JSON.stringify(outcome.body)],
    );
    return outcome;
  });
}

async function refundPayment(
  tx: Transaction,
  { merchantId, paymentId, amountMinor }: RefundCommand,
  hooks: RefundHooks,
): Promise<ServiceResponse> {
  const updated = await tx.query<{ amount_minor: number; refunded_minor: number; currency: string }>(
    `UPDATE payments SET refunded_minor = refunded_minor + $3
      WHERE id = $1 AND merchant_id = $2 AND refunded_minor + $3 <= amount_minor
      RETURNING amount_minor::integer, refunded_minor::integer, currency`,
    [paymentId, merchantId, amountMinor],
  );
  const payment = updated.rows[0];
  if (!payment) {
    const current = await tx.query<{ amount_minor: number; refunded_minor: number }>(
      `SELECT amount_minor::integer, refunded_minor::integer FROM payments
        WHERE id = $1 AND merchant_id = $2`,
      [paymentId, merchantId],
    );
    const row = current.rows[0];
    // Another merchant's payment is "not found" - its existence is not revealed.
    if (!row) return problem(404, 'payment-not-found', 'Payment not found');
    return problem(409, 'refund-exceeds-refundable', 'Refund exceeds the refundable amount', {
      refundableMinor: row.amount_minor - row.refunded_minor,
    });
  }

  const inserted = await tx.query<{ id: number }>(
    'INSERT INTO refunds (payment_id, amount_minor) VALUES ($1, $2) RETURNING id',
    [paymentId, amountMinor],
  );
  await hooks.afterRefund?.(tx);
  return {
    status: 201,
    body: {
      refundId: inserted.rows[0]!.id,
      paymentId,
      amountMinor,
      currency: payment.currency,
      refundableMinor: payment.amount_minor - payment.refunded_minor,
    },
    replayed: false,
  };
}

function problem(
  status: number,
  name: string,
  title: string,
  extra: Record<string, unknown> = {},
): ServiceResponse {
  return { status, body: { type: `${PROBLEMS}${name}`, title, status, ...extra }, replayed: false };
}
