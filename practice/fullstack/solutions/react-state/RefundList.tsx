// Reference solution (react-state-and-effects): a refund list for the SandPay merchant dashboard.
import { useState } from 'react';

export type RefundLine = {
  id: string;
  label: string;
  /** Price of one unit in minor units (cents) - integers, never floating point. */
  unitMinor: number;
  quantity: number;
};

/** 1250 -> "12.50" without floating-point arithmetic. */
export function formatMinor(minor: number): string {
  return `${Math.floor(minor / 100)}.${String(minor % 100).padStart(2, '0')}`;
}

function totalOf(lines: readonly RefundLine[]): number {
  return lines.reduce((sum, line) => sum + line.unitMinor * line.quantity, 0);
}

/** Returns a new array with a new object for the changed line; nothing is mutated. */
function addQuantity(lines: RefundLine[], id: string, amount: number): RefundLine[] {
  return lines.map((l) => (l.id === id ? { ...l, quantity: l.quantity + amount } : l));
}

export function RefundList({ initialLines }: { initialLines: readonly RefundLine[] }) {
  // initialLines only seeds the state; the array is copied, the line objects are never changed.
  const [lines, setLines] = useState<RefundLine[]>(() => [...initialLines]);
  // Derived, not stored: computing it during rendering means it can never be out of date.
  const total = totalOf(lines);

  function oneMore(id: string) {
    setLines((current) => addQuantity(current, id, 1));
  }

  function addThree(id: string) {
    // Updater functions are queued and each receives the result of the previous one.
    for (let i = 0; i < 3; i++) setLines((current) => addQuantity(current, id, 1));
  }

  function remove(id: string) {
    setLines((current) => current.filter((l) => l.id !== id));
  }

  return (
    <section aria-label="Refund">
      <ul>
        {lines.map((line) => (
          <li key={line.id} aria-label={line.label}>
            <span>
              {line.label} x {line.quantity}
            </span>
            <button type="button" aria-label={`One more ${line.label}`} onClick={() => oneMore(line.id)}>
              +1
            </button>
            <button type="button" aria-label={`Add three ${line.label}`} onClick={() => addThree(line.id)}>
              +3
            </button>
            <button type="button" aria-label={`Remove ${line.label}`} onClick={() => remove(line.id)}>
              Remove
            </button>
          </li>
        ))}
      </ul>
      <p>Total: {formatMinor(total)} EUR</p>
    </section>
  );
}
