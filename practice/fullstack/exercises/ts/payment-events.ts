// The payment timeline of the SandPay merchant dashboard (fictional). The API sends a stream of
// payment events; the dashboard folds them into one view per payment.

/** Every event the dashboard receives - a discriminated union on `type`. */
export type PaymentEvent =
  | { type: 'authorized'; paymentId: string; amountMinor: number }
  | { type: 'captured'; paymentId: string; amountMinor: number }
  | { type: 'refunded'; paymentId: string; amountMinor: number; reason: string }
  | { type: 'failed'; paymentId: string; code: string };

export type PaymentStatus = 'authorized' | 'captured' | 'partially_refunded' | 'refunded' | 'failed';

export interface PaymentView {
  readonly paymentId: string;
  readonly status: PaymentStatus;
  readonly authorizedMinor: number;
  readonly capturedMinor: number;
  readonly refundedMinor: number;
  readonly failureCode?: string;
}

/** Called in the default branch of an exhaustive switch: compiles only if every case is handled. */
export function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${JSON.stringify(value)}`);
}

/**
 * Applies one event to the payment's current view (undefined before the first event) and returns a
 * new view; never mutates the old one. Rules:
 * - authorized: starts a view (status authorized, nothing captured or refunded);
 * - captured: needs an existing view; captures up to the authorized amount (more is a RangeError);
 * - refunded: needs an existing view; adds to refundedMinor; the total may not exceed capturedMinor
 *   (RangeError); status becomes refunded when everything captured is refunded, else partially_refunded;
 * - failed: status failed with the failure code (a view is created if there was none, with zero amounts);
 * - any other event for an unknown payment throws an Error naming the payment id.
 */
export function applyEvent(view: PaymentView | undefined, event: PaymentEvent): PaymentView {
  // TODO: switch on event.type and apply the rules above. Finish with an exhaustive default branch.
  if (view) return view;
  return {
    paymentId: event.paymentId,
    status: 'authorized',
    authorizedMinor: 0,
    capturedMinor: 0,
    refundedMinor: 0,
  };
}

function existing(view: PaymentView | undefined, paymentId: string): PaymentView {
  if (!view) throw new Error(`No payment ${paymentId} - the first event must be authorized or failed`);
  return view;
}

/** One line for the dashboard's activity feed. Amounts are minor units, shown as-is. */
export function describeEvent(event: PaymentEvent): string {
  // TODO: one line per event type, as in the tests. Use assertNever so a new event type can't be missed.
  return event.paymentId;
}
