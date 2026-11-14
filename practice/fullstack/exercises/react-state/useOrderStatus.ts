// Exercise (react-state-and-effects): a hook that loads a SandPay order's status for the dashboard.
// It works for one order that loads quickly, but it is wrong when the order id changes, when a response
// is slow, when a request fails and in Strict Mode. Make every test in
// tests/react-state/use-order-status.test.tsx pass. Keep the exported types and the signature.
import { useEffect, useState } from 'react';

export type OrderStatus = 'PENDING' | 'PAID' | 'FAILED';

/** Loads one order's status. Must stop (reject) when `signal` is aborted. */
export type FetchStatus = (orderId: string, signal: AbortSignal) => Promise<OrderStatus>;

export type OrderStatusState =
  { status: 'loading' } | { status: 'loaded'; value: OrderStatus } | { status: 'error'; message: string };

/** `fetchStatus` must be stable (defined outside the component, or memoised) - it is an Effect dependency. */
export function useOrderStatus(orderId: string, fetchStatus: FetchStatus): OrderStatusState {
  const [state, setState] = useState<OrderStatusState>({ status: 'loading' });

  useEffect(() => {
    void fetchStatus(orderId, new AbortController().signal).then((value) => {
      setState({ status: 'loaded', value });
    });
  }, [orderId, fetchStatus]);

  return state;
}
