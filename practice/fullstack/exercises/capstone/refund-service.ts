// Capstone exercise 1: an idempotent refund in one PostgreSQL transaction.
// Tests: tests/capstone/refund-service.test.ts. Do this one first - the API (exercise 2) calls it.
//
// createRefund(db, command) refunds part of a payment for a merchant, at most once per idempotency key.
// It returns the HTTP status and body the API will send, and whether the answer was replayed.
//
// The contract, rule by rule (SandPay's, following draft-ietf-httpapi-idempotency-key-header-08):
// - Keys are scoped to the merchant: the same key from two merchants is two different requests.
// - The request's fingerprint is fingerprintOf(command) (given below) - paymentId and amountMinor.
// - First use of a key -> do the refund, store the status code and body with the key, return them.
// - Same key, same fingerprint, outcome stored -> return the stored status and body, replayed: true,
//   and change nothing.
// - Same key, different fingerprint -> 422 problem `idempotency-key-reused`; change nothing.
// - Same key, outcome not stored yet -> 409 problem `request-in-progress`.
// - The refund itself (lessons transactions-and-isolation and owasp-top-10-for-developers):
//   * a payment that doesn't exist or belongs to another merchant -> 404 `payment-not-found`
//   * more than is left to refund -> 409 `refund-exceeds-refundable` with `refundableMinor`
//   * success -> 201 with { refundId, paymentId, amountMinor, currency, refundableMinor } where
//     refundableMinor is what is left after this refund; a row in `refunds`; payments.refunded_minor grows.
// - Business outcomes (201, 404, 409 exceeds) are stored and replayed - a retry gets the same answer.
// - All of it in ONE transaction: if anything throws (hooks.afterRefund in the tests), nothing is
//   kept - not the refund, not the key - so a retry with the same key works.
// - Two calls with the same key at the same moment (Promise.all) -> exactly one refund.
//
// Problems are Problem Details (RFC 9457) bodies: { type: `${PROBLEMS}<name>`, title, status, ...extras }.
// Validation of amountMinor and the key's presence is the API's job, not this function's.
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
  // A first draft that "works" when nothing goes wrong: it looks the key up, then refunds, then stores
  // the key - three separate steps, no transaction, no fingerprint, no merchant check on the payment.
  // TODO: replace it with the contract above.
  const seen = await db.query<{ status_code: number; response: Record<string, unknown> }>(
    'SELECT status_code, response FROM idempotency_keys WHERE key = $1',
    [command.idempotencyKey],
  );
  if (seen.rows[0]) return { status: seen.rows[0].status_code, body: seen.rows[0].response, replayed: true };

  const payment = await db.query<{ amount_minor: number; refunded_minor: number; currency: string }>(
    'SELECT amount_minor::integer, refunded_minor::integer, currency FROM payments WHERE id = $1',
    [command.paymentId],
  );
  const row = payment.rows[0];
  if (!row) return { status: 404, body: { title: 'Payment not found', status: 404 }, replayed: false };
  await db.query('UPDATE payments SET refunded_minor = refunded_minor + $2 WHERE id = $1', [
    command.paymentId,
    command.amountMinor,
  ]);
  const inserted = await db.query<{ id: number }>(
    'INSERT INTO refunds (payment_id, amount_minor) VALUES ($1, $2) RETURNING id',
    [command.paymentId, command.amountMinor],
  );
  void hooks;
  const body = {
    refundId: inserted.rows[0]!.id,
    paymentId: command.paymentId,
    amountMinor: command.amountMinor,
    currency: row.currency,
  };
  await db.query(
    'INSERT INTO idempotency_keys (merchant_id, key, fingerprint, status_code, response) VALUES ($1, $2, $3, 201, $4)',
    [command.merchantId, command.idempotencyKey, '', JSON.stringify(body)],
  );
  return { status: 201, body, replayed: false };
}
