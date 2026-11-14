// Refund requests arrive at the SandPay merchant dashboard (fictional) as JSON - `unknown` until
// checked. TypeScript types disappear at runtime, so the code must check the data itself.

/** A value or a list of problems - the caller must check `ok` before using either. */
export type Result<T, E> = { ok: true; value: T } | { ok: false; error: E };

export const ok = <T>(value: T): Result<T, never> => ({ ok: true, value });
export const err = <E>(error: E): Result<never, E> => ({ ok: false, error });

export interface RefundRequest {
  paymentId: string;
  amountMinor: number;
  currency: 'EUR' | 'GBP' | 'INR' | 'USD';
  reason?: string;
}

const CURRENCIES: readonly RefundRequest['currency'][] = ['EUR', 'GBP', 'INR', 'USD'];

const isCurrency = (value: unknown): value is RefundRequest['currency'] =>
  typeof value === 'string' && (CURRENCIES as readonly string[]).includes(value);

/**
 * Checks untrusted input. On success returns a RefundRequest with only the known fields; otherwise
 * every problem, each naming its field:
 * - the input must be a non-null object (else the single error "body: must be an object");
 * - paymentId: a string starting with "pay_";
 * - amountMinor: a positive safe integer (minor units, never a decimal);
 * - currency: one of EUR, GBP, INR, USD;
 * - reason: optional; if present, a string of at most 200 characters.
 */
export function parseRefundRequest(input: unknown): Result<RefundRequest, string[]> {
  if (typeof input !== 'object' || input === null) return err(['body: must be an object']);
  const body = input as Record<string, unknown>;
  const errors: string[] = [];

  const { paymentId, amountMinor, currency, reason } = body;
  if (typeof paymentId !== 'string' || !paymentId.startsWith('pay_'))
    errors.push('paymentId: must be a string starting with pay_');
  if (typeof amountMinor !== 'number' || !Number.isSafeInteger(amountMinor) || amountMinor <= 0)
    errors.push('amountMinor: must be a positive integer');
  if (!isCurrency(currency)) errors.push(`currency: must be one of ${CURRENCIES.join(', ')}`);
  if (reason !== undefined && (typeof reason !== 'string' || reason.length > 200))
    errors.push('reason: must be a string of at most 200 characters');

  if (errors.length > 0) return err(errors);
  const request: RefundRequest = {
    paymentId: paymentId as string,
    amountMinor: amountMinor as number,
    currency: currency as RefundRequest['currency'],
  };
  if (typeof reason === 'string') request.reason = reason;
  return ok(request);
}

/**
 * Groups items by a key. Keys that no item has are absent, so the result is a Partial record.
 * Items keep their input order inside each group.
 */
export function groupBy<T, K extends PropertyKey>(
  items: readonly T[],
  keyOf: (item: T) => K,
): Partial<Record<K, T[]>> {
  const groups: Partial<Record<K, T[]>> = {};
  for (const item of items) {
    const key = keyOf(item);
    (groups[key] ??= []).push(item);
  }
  return groups;
}
