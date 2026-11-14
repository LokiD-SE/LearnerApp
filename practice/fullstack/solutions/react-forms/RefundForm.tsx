// Reference solution (react-forms-and-validation): a refund form for the SandPay merchant dashboard.
import { useId, useRef, useState, type FormEvent } from 'react';

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

function validate(amount: string, reason: string, refundableMinor: number, currency: string): Errors {
  const errors: Errors = {};
  if (amount.trim() === '') errors.amount = 'Enter the amount to refund.';
  else {
    const minor = parseAmount(amount);
    if (minor === null) errors.amount = 'Enter the amount like 12.50.';
    else if (minor === 0) errors.amount = 'The amount must be more than 0.00.';
    else if (minor > refundableMinor)
      errors.amount = `You can refund at most ${formatMinor(refundableMinor)} ${currency}.`;
  }
  if (reason === '') errors.reason = 'Choose a reason.';
  return errors;
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
  const [errors, setErrors] = useState<Errors>({});
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);
  const [problem, setProblem] = useState('');
  const [refundId, setRefundId] = useState('');
  // A ref, not state: the in-flight guard must change before React re-renders.
  const inFlight = useRef(false);
  const key = useRef<string | null>(null);
  const amountRef = useRef<HTMLInputElement>(null);
  const reasonRef = useRef<HTMLSelectElement>(null);
  const id = useId();

  function focusFirst(found: Errors) {
    if (found.amount) amountRef.current?.focus();
    else if (found.reason) reasonRef.current?.focus();
  }

  function change(field: Field, value: string) {
    const next = { amount, reason, [field]: value };
    if (field === 'amount') setAmount(value);
    else setReason(value);
    key.current = null; // a different request needs a different key
    // After the first submit, re-check as the user corrects the field.
    if (submitted) setErrors(validate(next.amount, next.reason, refundableMinor, order.currency));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    setSubmitted(true);
    setProblem('');
    const found = validate(amount, reason, refundableMinor, order.currency);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      focusFirst(found);
      return;
    }
    inFlight.current = true;
    setPending(true);
    key.current ??= newKey();
    try {
      const result = await submitRefund({
        orderId: order.id,
        amountMinor: parseAmount(amount) ?? 0,
        reason,
        idempotencyKey: key.current,
      });
      if (result.ok) {
        setRefundId(result.refundId);
        key.current = null;
      } else {
        setErrors(result.fieldErrors);
        focusFirst(result.fieldErrors);
      }
    } catch {
      // The outcome is unknown: the refund may exist. Retrying with the same key is safe.
      setProblem('We could not reach SandPay. The refund may not have been created - try again.');
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  if (refundId) return <p role="status">Refund {refundId} created.</p>;

  const amountError = errors.amount;
  const reasonError = errors.reason;
  return (
    <form noValidate onSubmit={handleSubmit} aria-label={`Refund order ${order.id}`}>
      <p id={`${id}-hint`}>
        Refundable: {formatMinor(refundableMinor)} {order.currency}
      </p>
      <label htmlFor={`${id}-amount`}>Amount ({order.currency})</label>
      <input
        id={`${id}-amount`}
        ref={amountRef}
        name="amount"
        inputMode="decimal"
        value={amount}
        onChange={(e) => change('amount', e.target.value)}
        aria-invalid={amountError ? true : undefined}
        aria-describedby={amountError ? `${id}-hint ${id}-amount-error` : `${id}-hint`}
      />
      {amountError && <p id={`${id}-amount-error`}>{amountError}</p>}

      <label htmlFor={`${id}-reason`}>Reason</label>
      <select
        id={`${id}-reason`}
        ref={reasonRef}
        name="reason"
        value={reason}
        onChange={(e) => change('reason', e.target.value)}
        aria-invalid={reasonError ? true : undefined}
        aria-describedby={reasonError ? `${id}-reason-error` : undefined}
      >
        <option value="">Choose...</option>
        {REASONS.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      {reasonError && <p id={`${id}-reason-error`}>{reasonError}</p>}

      {problem && <p role="alert">{problem}</p>}
      <button type="submit" disabled={pending}>
        {pending ? 'Refunding...' : 'Refund'}
      </button>
    </form>
  );
}
