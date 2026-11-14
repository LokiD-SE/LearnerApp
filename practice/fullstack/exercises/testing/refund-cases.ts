import type { RefundDecision, RefundRequest } from './refund-rules.js';

/** One row of a table-driven test: an input and the decision the rules must make for it. */
export interface RefundCase {
  name: string;
  input: RefundRequest;
  expected: RefundDecision;
}

/**
 * TODO: write the cases that would catch a broken decideRefund (read its rules in refund-rules.ts).
 * The checker runs every case against the real rules - each must pass - and against seven broken
 * versions ("mutants"); at least one of your cases must fail on each. Use at most 10 cases: pick
 * boundaries and combinations, not random values.
 */
export const refundCases: RefundCase[] = [
  {
    name: 'a partial refund of a fresh payment is accepted',
    input: { capturedMinor: 10000, refundedMinor: 0, requestedMinor: 2500, paymentAgeDays: 3 },
    expected: { ok: true, remainingAfterMinor: 7500 },
  },
];
