// Reference solution (react-state-and-effects): a hook that loads a SandPay order's status.
import { useEffect, useState } from 'react';

export type OrderStatus = 'PENDING' | 'PAID' | 'FAILED';

/** Loads one order's status. Must stop (reject) when `signal` is aborted. */
export type FetchStatus = (orderId: string, signal: AbortSignal) => Promise<OrderStatus>;

export type OrderStatusState =
  { status: 'loading' } | { status: 'loaded'; value: OrderStatus } | { status: 'error'; message: string };

type Settled = Exclude<OrderStatusState, { status: 'loading' }>;

/** `fetchStatus` must be stable (defined outside the component, or memoised) - it is an Effect dependency. */
export function useOrderStatus(orderId: string, fetchStatus: FetchStatus): OrderStatusState {
  // Remember which order a result belongs to. "Loading" is then derived during rendering: a result for
  // another order is never shown, and no Effect has to reset the state when orderId changes.
  const [result, setResult] = useState<{ forId: string; outcome: Settled } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let ignore = false;
    fetchStatus(orderId, controller.signal).then(
      (value) => {
        if (!ignore) setResult({ forId: orderId, outcome: { status: 'loaded', value } });
      },
      (error: unknown) => {
        // An aborted or superseded request is not an error the user should see.
        if (ignore) return;
        const message = error instanceof Error ? error.message : String(error);
        setResult({ forId: orderId, outcome: { status: 'error', message } });
      },
    );
    // Cleanup runs before the Effect runs again for a new orderId, on unmount, and in Strict Mode's
    // extra development-only setup + cleanup cycle.
    return () => {
      ignore = true;
      controller.abort();
    };
  }, [orderId, fetchStatus]);

  if (result === null || result.forId !== orderId) return { status: 'loading' };
  return result.outcome;
}
