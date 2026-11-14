// Exercise (react-state-and-effects): a refund list for the SandPay merchant dashboard.
// It renders correctly the first time, but it has three state bugs. Fix them so that every test in
// tests/react-state/refund-list.test.tsx passes. Keep the markup (names and labels) as it is.
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

export function RefundList({ initialLines }: { initialLines: readonly RefundLine[] }) {
  const [lines, setLines] = useState<RefundLine[]>([...initialLines]);
  const [total] = useState(totalOf(initialLines));

  function oneMore(id: string) {
    const line = lines.find((l) => l.id === id);
    if (!line) return;
    line.quantity += 1;
    setLines(lines);
  }

  function addThree(id: string) {
    for (let i = 0; i < 3; i++) {
      setLines(lines.map((l) => (l.id === id ? { ...l, quantity: l.quantity + 1 } : l)));
    }
  }

  function remove(id: string) {
    setLines(lines.filter((l) => l.id !== id));
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
