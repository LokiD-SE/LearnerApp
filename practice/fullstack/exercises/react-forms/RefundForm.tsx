// Exercise (react-forms-and-validation): a refund form for the SandPay merchant dashboard.
// It renders and it sends a request, but that is all. Make every test in
// tests/react-forms/refund-form.test.tsx pass:
//   - validate on submit (empty amount, format like 12.50, more than 0.00, at most the refundable amount,
//     a reason) and send nothing while there are errors;
//   - show each error as text, mark the field aria-invalid and point aria-describedby at the error;
//     move focus to the first invalid field; after a failed submit, re-check as the user corrects a field;
//   - send amounts in minor units (parseAmount, never floating point) and one request at a time, with the
//     button disabled and reading "Refunding..." while it runs;
//   - show the API's field errors, a "Refund re_... created." status after success, and an alert after a
//     network failure - where a retry of the same request must reuse the same idempotency key.
// Keep the labels, the button name and the exported types. Messages are listed in the tests.
import { useId, useState, type FormEvent } from 'react';

export type RefundOrder = {
  id: string;
  currency: string;
  /** Captured amount, in minor units (cents). */
  capturedMinor: number;
  /** Already refunded, in minor units. */
  refundedMinor: number;
};

export type RefundRequest = {
  orderId: string;
  amountMinor: number;
  reason: string;
  idempotencyKey: string;
};

/** What the (fake) SandPay API answers. A network failure rejects the promise instead. */
export type RefundResult =
  { ok: true; refundId: string } | { ok: false; fieldErrors: Partial<Record<'amount' | 'reason', string>> };

type Field = 'amount' | 'reason';
type Errors = Partial<Record<Field, string>>;

export const REASONS = [
  { value: 'requested_by_customer', label: 'Requested by customer' },
  { value: 'duplicate', label: 'Duplicate payment' },
  { value: 'damaged', label: 'Damaged goods' },
] as const;

/** 1250 -> "12.50" without floating-point arithmetic. */
export function formatMinor(minor: number): string {
  return `${Math.floor(minor / 100)}.${String(minor % 100).padStart(2, '0')}`;
}

/** "12.5" -> 1250; null when the text is not a plain amount with at most two decimals. */
export function parseAmount(text: string): number | null {
  const match = /^(\d{1,7})(?:\.(\d{1,2}))?$/.exec(text.trim());
  if (!match) return null;
  const units = Number(match[1]);
  const cents = Number((match[2] ?? '').padEnd(2, '0'));
  return units * 100 + cents;
}

export function RefundForm({
  order,
  submitRefund,
  newKey,
}: {
  order: RefundOrder;
  submitRefund: (request: RefundRequest) => Promise<RefundResult>;
  /** Makes a new idempotency key (crypto.randomUUID in the app; predictable in tests). */
  newKey: () => string;
}) {
  const refundableMinor = order.capturedMinor - order.refundedMinor;
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const id = useId();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitRefund({
      orderId: order.id,
      amountMinor: Math.round(Number(amount) * 100),
      reason,
      idempotencyKey: newKey(),
    });
  }

  return (
    <form noValidate onSubmit={handleSubmit} aria-label={`Refund order ${order.id}`}>
      <p id={`${id}-hint`}>
        Refundable: {formatMinor(refundableMinor)} {order.currency}
      </p>
      <label htmlFor={`${id}-amount`}>Amount ({order.currency})</label>
      <input
        id={`${id}-amount`}
        name="amount"
        inputMode="decimal"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        aria-describedby={`${id}-hint`}
      />

      <label htmlFor={`${id}-reason`}>Reason</label>
      <select id={`${id}-reason`} name="reason" value={reason} onChange={(e) => setReason(e.target.value)}>
        <option value="">Choose...</option>
        {REASONS.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>

      <button type="submit">Refund</button>
    </form>
  );
}
