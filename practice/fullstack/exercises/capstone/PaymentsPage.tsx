// Capstone exercise 3: the dashboard's payments page (React 19).
// Tests: tests/capstone/payments-page.test.tsx
//
// The page talks to the API through `client` (in the app, a fetch wrapper for exercise 2's routes).
// The draft below shows the payments when everything goes well. Make it meet the whole contract:
//
// - Loading: <p role="status">Loading payments...</p>.
// - Loading failed: role="alert" containing "Could not load payments." and a "Retry" button that loads again.
// - No payments: "No payments yet."
// - A table with the caption "Payments" and a row per payment: id (row header), date (YYYY-MM-DD from
//   createdAt), amount and refundable amount formatted with formatMoney, and an action:
//   * refundable > 0: a button named "Refund <refundable> on <id>", e.g. "Refund €12.50 on pay_1002",
//     which refunds everything that is left;
//   * otherwise the text "Fully refunded".
// - A refund click makes ONE key with newKey() and calls client.refund(id, refundableMinor, key).
//   While a refund is in flight, every refund button is disabled - a double click refunds once.
// - { ok: true, refundableMinor } -> the row shows the new refundable amount (and "Fully refunded" at
//   0), and a role="status" element says "Refunded €12.50 on pay_1002."
// - { ok: false, title } -> role="alert" "Refund failed: <title>". The server answered, so there is
//   no "Try again".
// - client.refund throws (no answer - network error, time-out) -> role="alert" saying
//   "The refund on <id> did not complete. Try again - it will not be refunded twice." with a "Try again"
//   button that sends the SAME paymentId, amount and key again. A new refund click makes a new key.
import { useEffect, useState, type ReactElement } from 'react';

export interface PaymentRow {
  id: string;
  amountMinor: number;
  currency: string;
  refundedMinor: number;
  refundableMinor: number;
  createdAt: string;
}

export type RefundResult = { ok: true; refundableMinor: number } | { ok: false; title: string };

export interface DashboardClient {
  listPayments(): Promise<PaymentRow[]>;
  refund(paymentId: string, amountMinor: number, idempotencyKey: string): Promise<RefundResult>;
}

export interface PaymentsPageProps {
  client: DashboardClient;
  /** Makes a new idempotency key; the app passes () => crypto.randomUUID(). */
  newKey: () => string;
}

export function formatMoney(amountMinor: number, currency: string): string {
  return new Intl.NumberFormat('en-IE', { style: 'currency', currency }).format(amountMinor / 100);
}

export function PaymentsPage({ client, newKey }: PaymentsPageProps): ReactElement {
  const [payments, setPayments] = useState<PaymentRow[]>([]);

  useEffect(() => {
    void client.listPayments().then(setPayments);
  }, [client]);

  async function refund(p: PaymentRow): Promise<void> {
    const result = await client.refund(p.id, p.refundableMinor, newKey());
    if (result.ok) {
      setPayments((rows) =>
        rows.map((row) => (row.id === p.id ? { ...row, refundableMinor: result.refundableMinor } : row)),
      );
    }
  }

  return (
    <table>
      <caption>Payments</caption>
      <tbody>
        {payments.map((p) => (
          <tr key={p.id}>
            <th scope="row">{p.id}</th>
            <td>{formatMoney(p.amountMinor, p.currency)}</td>
            <td>
              <button type="button" onClick={() => void refund(p)}>
                Refund {formatMoney(p.refundableMinor, p.currency)} on {p.id}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
