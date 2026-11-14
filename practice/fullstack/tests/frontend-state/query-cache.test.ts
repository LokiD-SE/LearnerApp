import { createQueryCache } from '../../exercises/frontend-state/queryCache.js';

/** A clock the test moves by hand - no timers, no waiting. */
function fakeClock(start = 1_000) {
  let time = start;
  return { now: () => time, advance: (ms: number) => void (time += ms) };
}

/** A fetcher that counts calls and answers when the test says so. */
function deferredFetcher<T>() {
  const calls: { resolve: (value: T) => void; reject: (error: Error) => void }[] = [];
  const fetcher = () =>
    new Promise<T>((resolve, reject) => {
      calls.push({ resolve, reject });
    });
  return { calls, fetcher };
}

describe('createQueryCache', { tags: ['@exercise'] }, () => {
  it('keeps data fresh until staleTime has elapsed, then reports it stale', () => {
    const clock = fakeClock();
    const cache = createQueryCache({ now: clock.now, staleTime: 30_000 });
    expect(cache.isStale(['orders'])).toBe(true); // nothing stored yet
    cache.set(['orders'], ['ord_1001']);
    clock.advance(29_999);
    expect(cache.isStale(['orders'])).toBe(false);
    clock.advance(1);
    expect(cache.isStale(['orders'])).toBe(true);
    expect(cache.get(['orders'])?.data).toEqual(['ord_1001']); // stale data is still there to show
  });

  it('serves fresh data from the cache without calling the fetcher', async () => {
    const clock = fakeClock();
    const cache = createQueryCache({ now: clock.now, staleTime: 30_000 });
    let calls = 0;
    const fetcher = async () => {
      calls += 1;
      return { id: 'ord_1001', status: 'PAID' };
    };
    await cache.fetchQuery(['order', 'ord_1001'], fetcher);
    clock.advance(10_000);
    const second = await cache.fetchQuery(['order', 'ord_1001'], fetcher);
    expect(second).toEqual({ id: 'ord_1001', status: 'PAID' });
    expect(calls).toBe(1);
  });

  it('refetches stale data and stores the new value with the new time', async () => {
    const clock = fakeClock();
    const cache = createQueryCache({ now: clock.now, staleTime: 30_000 });
    await cache.fetchQuery(['order', 'ord_1001'], async () => 'PENDING');
    clock.advance(30_000);
    const fresh = await cache.fetchQuery(['order', 'ord_1001'], async () => 'PAID');
    expect(fresh).toBe('PAID');
    expect(cache.get(['order', 'ord_1001'])).toEqual({ data: 'PAID', updatedAt: 31_000 });
  });

  it('sends one request when several components ask for the same stale key at once', async () => {
    const cache = createQueryCache({ now: fakeClock().now, staleTime: 30_000 });
    const server = deferredFetcher<string>();
    const first = cache.fetchQuery(['order', 'ord_1001'], server.fetcher);
    const second = cache.fetchQuery(['order', 'ord_1001'], server.fetcher);
    expect(server.calls).toHaveLength(1);
    server.calls[0]?.resolve('PAID');
    expect(await first).toBe('PAID');
    expect(await second).toBe('PAID');
    // After it settles, a stale key may be requested again.
    cache.invalidate(['order', 'ord_1001']);
    void cache.fetchQuery(['order', 'ord_1001'], server.fetcher);
    expect(server.calls).toHaveLength(2);
  });

  it('a failed request is not cached, and the next call tries again', async () => {
    const cache = createQueryCache({ now: fakeClock().now, staleTime: 30_000 });
    await expect(
      cache.fetchQuery(['order', 'ord_1001'], () => Promise.reject(new Error('503 Service Unavailable'))),
    ).rejects.toThrow('503');
    expect(cache.get(['order', 'ord_1001'])).toBeUndefined();
    expect(await cache.fetchQuery(['order', 'ord_1001'], async () => 'PAID')).toBe('PAID');
  });

  it('invalidates every key that starts with the prefix, and only those', () => {
    const cache = createQueryCache({ now: fakeClock().now, staleTime: 30_000 });
    cache.set(['orders', 'PAID', 1], ['ord_1001']);
    cache.set(['orders', 'PAID', 2], ['ord_1003']);
    cache.set(['orders', 'FAILED', 1], ['ord_1002']);
    cache.set(['refunds', 1], ['ref_2001']);
    cache.invalidate(['orders', 'PAID']);
    expect(cache.isStale(['orders', 'PAID', 1])).toBe(true);
    expect(cache.isStale(['orders', 'PAID', 2])).toBe(true);
    expect(cache.isStale(['orders', 'FAILED', 1])).toBe(false);
    expect(cache.isStale(['refunds', 1])).toBe(false);
    cache.invalidate(['orders']);
    expect(cache.isStale(['orders', 'FAILED', 1])).toBe(true);
    expect(cache.isStale(['refunds', 1])).toBe(false);
  });

  it('shows an optimistic update at once and invalidates the key when the server accepts it', async () => {
    const cache = createQueryCache({ now: fakeClock().now, staleTime: 30_000 });
    cache.set(['order', 'ord_1001'], { status: 'PAID', refunded: 0 });
    let finish!: () => void;
    const done = cache.mutateOptimistic<{ status: string; refunded: number }>(
      ['order', 'ord_1001'],
      (old) => ({ status: 'REFUNDED', refunded: (old?.refunded ?? 0) + 1500 }),
      () => new Promise<void>((resolve) => (finish = resolve)),
    );
    expect(cache.get(['order', 'ord_1001'])?.data).toEqual({ status: 'REFUNDED', refunded: 1500 });
    finish();
    await done;
    expect(cache.isStale(['order', 'ord_1001'])).toBe(true); // refetch the server's truth next time
  });

  it('rolls back exactly to the previous entry when the server rejects the change', async () => {
    const clock = fakeClock();
    const cache = createQueryCache({ now: clock.now, staleTime: 30_000 });
    cache.set(['order', 'ord_1001'], { status: 'PAID' });
    clock.advance(5_000);
    await expect(
      cache.mutateOptimistic(
        ['order', 'ord_1001'],
        () => ({ status: 'REFUNDED' }),
        () => Promise.reject(new Error('409 Conflict')),
      ),
    ).rejects.toThrow('409');
    expect(cache.get(['order', 'ord_1001'])).toEqual({ data: { status: 'PAID' }, updatedAt: 1_000 });
    expect(cache.isStale(['order', 'ord_1001'])).toBe(false);
  });

  it('removes an optimistic entry that had nothing before it when the change fails', async () => {
    const cache = createQueryCache({ now: fakeClock().now, staleTime: 30_000 });
    await expect(
      cache.mutateOptimistic(
        ['order', 'ord_9999'],
        () => ({ status: 'PENDING' }),
        () => Promise.reject(new Error('422 Unprocessable Content')),
      ),
    ).rejects.toThrow('422');
    expect(cache.get(['order', 'ord_9999'])).toBeUndefined();
  });
});
