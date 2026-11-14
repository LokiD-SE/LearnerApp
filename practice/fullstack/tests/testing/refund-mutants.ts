// Seven broken versions of decideRefund - each with one realistic bug. A good set of cases makes
// every one of them give a wrong answer somewhere. (Not a test file: the checker imports it.)
import {
  REFUND_WINDOW_DAYS,
  type RefundDecision,
  type RefundRequest,
} from '../../exercises/testing/refund-rules.js';

export interface Mutant {
  bug: string;
  decide: (r: RefundRequest) => RefundDecision;
}

const invalid = { ok: false, reason: 'invalid_amount' } as const;
const closed = { ok: false, reason: 'refund_window_closed' } as const;
const exceeds = { ok: false, reason: 'exceeds_refundable' } as const;

export const refundMutants: Mutant[] = [
  {
    bug: 'accepts a zero amount (< 0 instead of <= 0)',
    decide: (r) => {
      if (!Number.isSafeInteger(r.requestedMinor) || r.requestedMinor < 0) return invalid;
      if (r.paymentAgeDays > REFUND_WINDOW_DAYS) return closed;
      const refundable = r.capturedMinor - r.refundedMinor;
      if (r.requestedMinor > refundable) return exceeds;
      return { ok: true, remainingAfterMinor: refundable - r.requestedMinor };
    },
  },
  {
    bug: 'accepts fractions of a minor unit (no whole-number check)',
    decide: (r) => {
      if (r.requestedMinor <= 0) return invalid;
      if (r.paymentAgeDays > REFUND_WINDOW_DAYS) return closed;
      const refundable = r.capturedMinor - r.refundedMinor;
      if (r.requestedMinor > refundable) return exceeds;
      return { ok: true, remainingAfterMinor: refundable - r.requestedMinor };
    },
  },
  {
    bug: 'closes the window one day early (>= instead of >)',
    decide: (r) => {
      if (!Number.isSafeInteger(r.requestedMinor) || r.requestedMinor <= 0) return invalid;
      if (r.paymentAgeDays >= REFUND_WINDOW_DAYS) return closed;
      const refundable = r.capturedMinor - r.refundedMinor;
      if (r.requestedMinor > refundable) return exceeds;
      return { ok: true, remainingAfterMinor: refundable - r.requestedMinor };
    },
  },
  {
    bug: 'forgets earlier refunds (refundable = captured)',
    decide: (r) => {
      if (!Number.isSafeInteger(r.requestedMinor) || r.requestedMinor <= 0) return invalid;
      if (r.paymentAgeDays > REFUND_WINDOW_DAYS) return closed;
      const refundable = r.capturedMinor;
      if (r.requestedMinor > refundable) return exceeds;
      return { ok: true, remainingAfterMinor: refundable - r.requestedMinor };
    },
  },
  {
    bug: 'rejects refunding exactly what is left (>= instead of >)',
    decide: (r) => {
      if (!Number.isSafeInteger(r.requestedMinor) || r.requestedMinor <= 0) return invalid;
      if (r.paymentAgeDays > REFUND_WINDOW_DAYS) return closed;
      const refundable = r.capturedMinor - r.refundedMinor;
      if (r.requestedMinor >= refundable) return exceeds;
      return { ok: true, remainingAfterMinor: refundable - r.requestedMinor };
    },
  },
  {
    bug: 'reports the remainder before this refund (forgot to subtract it)',
    decide: (r) => {
      if (!Number.isSafeInteger(r.requestedMinor) || r.requestedMinor <= 0) return invalid;
      if (r.paymentAgeDays > REFUND_WINDOW_DAYS) return closed;
      const refundable = r.capturedMinor - r.refundedMinor;
      if (r.requestedMinor > refundable) return exceeds;
      return { ok: true, remainingAfterMinor: refundable };
    },
  },
  {
    bug: 'checks the amount before the window (wrong order of rules)',
    decide: (r) => {
      if (!Number.isSafeInteger(r.requestedMinor) || r.requestedMinor <= 0) return invalid;
      const refundable = r.capturedMinor - r.refundedMinor;
      if (r.requestedMinor > refundable) return exceeds;
      if (r.paymentAgeDays > REFUND_WINDOW_DAYS) return closed;
      return { ok: true, remainingAfterMinor: refundable - r.requestedMinor };
    },
  },
];
