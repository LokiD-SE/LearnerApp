import type { RefundDecision, RefundRequest } from './refund-rules.js';

/** One row of a table-driven test: an input and the decision the rules must make for it. */
export interface RefundCase {
  name: string;
  input: RefundRequest;
  expected: RefundDecision;
}

// Each case sits on a boundary or combines two rules, so a single off-by-one or a forgotten term
// changes its result. The comment names the bug each one is there to catch.
export const refundCases: RefundCase[] = [
  {
    // remaining = refundable - requested, with something already refunded (forgotten subtraction,
    // ignoring refundedMinor)
    name: 'a partial refund after an earlier refund leaves the right remainder',
    input: { capturedMinor: 10000, refundedMinor: 4000, requestedMinor: 2500, paymentAgeDays: 3 },
    expected: { ok: true, remainingAfterMinor: 3500 },
  },
  {
    // exactly what is left is allowed (> versus >=)
    name: 'refunding exactly what is left is accepted',
    input: { capturedMinor: 10000, refundedMinor: 4000, requestedMinor: 6000, paymentAgeDays: 3 },
    expected: { ok: true, remainingAfterMinor: 0 },
  },
  {
    // one minor unit more than is left (ignoring refundedMinor would accept it)
    name: 'one minor unit more than is left is rejected',
    input: { capturedMinor: 10000, refundedMinor: 4000, requestedMinor: 6001, paymentAgeDays: 3 },
    expected: { ok: false, reason: 'exceeds_refundable' },
  },
  {
    // the smallest invalid amount (< 0 instead of <= 0)
    name: 'a zero refund is invalid',
    input: { capturedMinor: 10000, refundedMinor: 0, requestedMinor: 0, paymentAgeDays: 3 },
    expected: { ok: false, reason: 'invalid_amount' },
  },
  {
    // a fraction of a minor unit (no whole-number check)
    name: 'a fractional amount is invalid',
    input: { capturedMinor: 10000, refundedMinor: 0, requestedMinor: 12.5, paymentAgeDays: 3 },
    expected: { ok: false, reason: 'invalid_amount' },
  },
  {
    // the last day of the window is still open (> versus >=)
    name: 'day 180 is still inside the refund window',
    input: { capturedMinor: 10000, refundedMinor: 0, requestedMinor: 100, paymentAgeDays: 180 },
    expected: { ok: true, remainingAfterMinor: 9900 },
  },
  {
    // two rules broken at once: the window rule is checked first (wrong order of checks)
    name: 'an old payment with too large an amount reports the closed window',
    input: { capturedMinor: 10000, refundedMinor: 0, requestedMinor: 20000, paymentAgeDays: 181 },
    expected: { ok: false, reason: 'refund_window_closed' },
  },
];
