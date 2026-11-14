// The code under test for the "cases that catch bugs" exercise. It is correct - don't change it.
// (The same file is in solutions/testing; the checker runs your cases against it and against mutants.)

/** A merchant asks SandPay to refund part or all of a captured card payment. Amounts are minor units. */
export interface RefundRequest {
  /** What was captured on the payment. */
  capturedMinor: number;
  /** What has already been refunded on it. */
  refundedMinor: number;
  /** What this refund asks for. */
  requestedMinor: number;
  /** Whole days since the capture. */
  paymentAgeDays: number;
}

export type RefundDecision =
  | { ok: true; remainingAfterMinor: number }
  | { ok: false; reason: 'invalid_amount' | 'refund_window_closed' | 'exceeds_refundable' };

/** Refunds are accepted up to and including day 180 after capture (SandPay's fictional rule). */
export const REFUND_WINDOW_DAYS = 180;

/**
 * The rules, checked in this order:
 * 1. the requested amount must be a whole number of minor units greater than zero - else invalid_amount;
 * 2. the payment must be at most REFUND_WINDOW_DAYS old - else refund_window_closed;
 * 3. the amount must not exceed what is still refundable (captured minus refunded) - else exceeds_refundable.
 * An accepted refund reports what will still be refundable after it.
 */
export function decideRefund(r: RefundRequest): RefundDecision {
  if (!Number.isSafeInteger(r.requestedMinor) || r.requestedMinor <= 0) {
    return { ok: false, reason: 'invalid_amount' };
  }
  if (r.paymentAgeDays > REFUND_WINDOW_DAYS) return { ok: false, reason: 'refund_window_closed' };
  const refundable = r.capturedMinor - r.refundedMinor;
  if (r.requestedMinor > refundable) return { ok: false, reason: 'exceeds_refundable' };
  return { ok: true, remainingAfterMinor: refundable - r.requestedMinor };
}
