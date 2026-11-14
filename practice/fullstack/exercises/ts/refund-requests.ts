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
  // TODO: narrow `input` step by step (typeof, null check, then each field) and collect every problem.
  void input;
  return err(['not implemented']);
}

/**
 * Groups items by a key. Keys that no item has are absent, so the result is a Partial record.
 * Items keep their input order inside each group.
 */
export function groupBy<T, K extends PropertyKey>(
  items: readonly T[],
  keyOf: (item: T) => K,
): Partial<Record<K, T[]>> {
  // TODO: one array per key, items in input order.
  void items;
  void keyOf;
  return {};
}
