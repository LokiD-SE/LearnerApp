// Reference solution: the dashboard's payments page. See the exercise file for the contract.
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

type Load = { state: 'loading' } | { state: 'failed' } | { state: 'ready'; payments: PaymentRow[] };

/** One refund the merchant asked for: its key is made once and reused by every retry. */
interface Attempt {
  paymentId: string;
  amountMinor: number;
  currency: string;
  key: string;
}

export function PaymentsPage({ client, newKey }: PaymentsPageProps): ReactElement {
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [reloads, setReloads] = useState(0);
  const [pending, setPending] = useState<Attempt | null>(null);
  const [interrupted, setInterrupted] = useState<Attempt | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    // A response that arrives after the component unmounted or reloaded is ignored (react.dev,
    // "Synchronizing with Effects" - fetching data).
    let ignore = false;
    setLoad({ state: 'loading' });
    client.listPayments().then(
      (payments) => {
        if (!ignore) setLoad({ state: 'ready', payments });
      },
      () => {
        if (!ignore) setLoad({ state: 'failed' });
      },
    );
    return () => {
      ignore = true;
    };
  }, [client, reloads]);

  async function run(attempt: Attempt): Promise<void> {
    setPending(attempt);
    setInterrupted(null);
    setMessage('');
    setError('');
    try {
      const result = await client.refund(attempt.paymentId, attempt.amountMinor, attempt.key);
      if (result.ok) {
        setLoad((current) =>
          current.state === 'ready'
            ? {
                state: 'ready',
                payments: current.payments.map((p) =>
                  p.id === attempt.paymentId
                    ? {
                        ...p,
                        refundableMinor: result.refundableMinor,
                        refundedMinor: p.amountMinor - result.refundableMinor,
                      }
                    : p,
                ),
              }
            : current,
        );
        setMessage(`Refunded ${formatMoney(attempt.amountMinor, attempt.currency)} on ${attempt.paymentId}.`);
      } else {
        // The server answered: retrying the same request would get the same answer.
        setError(`Refund failed: ${result.title}`);
      }
    } catch {
      // No answer (network error, time-out): the refund may or may not have happened. Keep the key.
      setInterrupted(attempt);
    } finally {
      setPending(null);
    }
  }

  if (load.state === 'loading') return <p role="status">Loading payments...</p>;
  if (load.state === 'failed') {
    return (
      <div role="alert">
        <p>Could not load payments.</p>
        <button type="button" onClick={() => setReloads((n) => n + 1)}>
          Retry
        </button>
      </div>
    );
  }
  if (load.payments.length === 0) return <p>No payments yet.</p>;

  return (
    <section aria-label="Payments">
      <p role="status">{message}</p>
      {error !== '' && <p role="alert">{error}</p>}
      {interrupted && (
        <div role="alert">
          <p>
            The refund on {interrupted.paymentId} did not complete. Try again - it will not be refunded twice.
          </p>
          <button type="button" disabled={pending !== null} onClick={() => void run(interrupted)}>
            Try again
          </button>
        </div>
      )}
      <table>
        <caption>Payments</caption>
        <thead>
          <tr>
            <th scope="col">Payment</th>
            <th scope="col">Date</th>
            <th scope="col">Amount</th>
            <th scope="col">Refundable</th>
            <th scope="col">Action</th>
          </tr>
        </thead>
        <tbody>
          {load.payments.map((p) => (
            <tr key={p.id}>
              <th scope="row">{p.id}</th>
              <td>{p.createdAt.slice(0, 10)}</td>
              <td>{formatMoney(p.amountMinor, p.currency)}</td>
              <td>{formatMoney(p.refundableMinor, p.currency)}</td>
              <td>
                {p.refundableMinor > 0 ? (
                  <button
                    type="button"
                    disabled={pending !== null}
                    onClick={() =>
                      void run({
                        paymentId: p.id,
                        amountMinor: p.refundableMinor,
                        currency: p.currency,
                        key: newKey(),
                      })
                    }
                  >
                    Refund {formatMoney(p.refundableMinor, p.currency)} on {p.id}
                  </button>
                ) : (
                  'Fully refunded'
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
