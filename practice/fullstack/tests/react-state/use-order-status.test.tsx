// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { StrictMode } from 'react';
import {
  useOrderStatus,
  type FetchStatus,
  type OrderStatus,
} from '../../exercises/react-state/useOrderStatus.js';

/** A fake server: every request waits until the test resolves or rejects it - no timers, no luck. */
function fakeServer() {
  const requests: {
    orderId: string;
    signal: AbortSignal;
    resolve: (status: OrderStatus) => void;
    reject: (error: Error) => void;
  }[] = [];
  const fetchStatus: FetchStatus = (orderId, signal) =>
    new Promise<OrderStatus>((resolve, reject) => {
      requests.push({ orderId, signal, resolve, reject });
    });
  return { requests, fetchStatus };
}

const req = <T,>(list: T[], i: number): T => {
  const item = list[i];
  if (item === undefined) throw new Error(`expected request #${i + 1}, but only ${list.length} were made`);
  return item;
};

describe('useOrderStatus', { tags: ['@exercise'] }, () => {
  it('is loading, then shows the loaded status', async () => {
    const server = fakeServer();
    const { result } = renderHook(() => useOrderStatus('ord_1001', server.fetchStatus));
    expect(result.current).toEqual({ status: 'loading' });
    expect(server.requests.map((r) => r.orderId)).toEqual(['ord_1001']);
    await act(async () => req(server.requests, 0).resolve('PAID'));
    expect(result.current).toEqual({ status: 'loaded', value: 'PAID' });
  });

  it('shows loading again as soon as the order id changes - never the previous order', async () => {
    const server = fakeServer();
    const { result, rerender } = renderHook(({ id }) => useOrderStatus(id, server.fetchStatus), {
      initialProps: { id: 'ord_1001' },
    });
    await act(async () => req(server.requests, 0).resolve('PAID'));
    rerender({ id: 'ord_1002' });
    expect(result.current).toEqual({ status: 'loading' });
  });

  it('ignores a slow response for an order that is no longer shown', async () => {
    const server = fakeServer();
    const { result, rerender } = renderHook(({ id }) => useOrderStatus(id, server.fetchStatus), {
      initialProps: { id: 'ord_1001' },
    });
    rerender({ id: 'ord_1002' });
    await act(async () => req(server.requests, 1).resolve('PENDING'));
    // The first request answers last. Its answer belongs to ord_1001 and must not replace ord_1002's.
    await act(async () => req(server.requests, 0).resolve('PAID'));
    expect(result.current).toEqual({ status: 'loaded', value: 'PENDING' });
  });

  it('aborts the previous request when the id changes, and the current one on unmount', () => {
    const server = fakeServer();
    const { rerender, unmount } = renderHook(({ id }) => useOrderStatus(id, server.fetchStatus), {
      initialProps: { id: 'ord_1001' },
    });
    rerender({ id: 'ord_1002' });
    expect(req(server.requests, 0).signal.aborted).toBe(true);
    expect(req(server.requests, 1).signal.aborted).toBe(false);
    unmount();
    expect(req(server.requests, 1).signal.aborted).toBe(true);
  });

  it('shows an error when the request fails', async () => {
    const server = fakeServer();
    const { result } = renderHook(() => useOrderStatus('ord_1001', server.fetchStatus));
    await act(async () => req(server.requests, 0).reject(new Error('503 Service Unavailable')));
    expect(result.current).toEqual({ status: 'error', message: '503 Service Unavailable' });
  });

  it('does not show an error for a request that was superseded', async () => {
    const server = fakeServer();
    const { result, rerender } = renderHook(({ id }) => useOrderStatus(id, server.fetchStatus), {
      initialProps: { id: 'ord_1001' },
    });
    rerender({ id: 'ord_1002' });
    await act(async () => req(server.requests, 0).reject(new Error('This operation was aborted')));
    expect(result.current).toEqual({ status: 'loading' });
    await act(async () => req(server.requests, 1).resolve('FAILED'));
    expect(result.current).toEqual({ status: 'loaded', value: 'FAILED' });
  });

  it('survives Strict Mode: the extra development-only setup and cleanup leave one live request', async () => {
    const server = fakeServer();
    const { result } = renderHook(() => useOrderStatus('ord_1001', server.fetchStatus), {
      wrapper: StrictMode,
    });
    // React runs setup, cleanup, setup in development: two requests, the first one cancelled.
    expect(server.requests.map((r) => r.orderId)).toEqual(['ord_1001', 'ord_1001']);
    expect(req(server.requests, 0).signal.aborted).toBe(true);
    expect(req(server.requests, 1).signal.aborted).toBe(false);
    await act(async () => req(server.requests, 1).resolve('PAID'));
    expect(result.current).toEqual({ status: 'loaded', value: 'PAID' });
  });
});
