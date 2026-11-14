// Exercise (frontend-state-management): a tiny server-state cache - the ideas behind TanStack Query, SWR
// and RTK Query, without a library. get and set work; staleness ignores time, invalidation only matches
// one exact key, every fetch goes to the network, and a failed optimistic update leaves wrong data on
// screen. Make every test in tests/frontend-state/query-cache.test.ts pass. Keep the exported names.

/** A query key: an array, like ['orders', { status: 'PAID' }] in the libraries - here strings and numbers. */
export type QueryKey = readonly (string | number)[];

export interface CacheEntry<T> {
  data: T;
  updatedAt: number;
}

export interface QueryCacheOptions {
  /** Current time in milliseconds (Date.now in the app, a fake clock in tests). */
  now: () => number;
  /** How long data stays fresh after it was stored, in milliseconds. */
  staleTime: number;
}

const hash = (key: QueryKey) => JSON.stringify(key);

export function createQueryCache({ now }: QueryCacheOptions) {
  const entries = new Map<string, { key: QueryKey; entry: CacheEntry<unknown>; invalidated: boolean }>();

  function get<T>(key: QueryKey): CacheEntry<T> | undefined {
    return entries.get(hash(key))?.entry as CacheEntry<T> | undefined;
  }

  function set<T>(key: QueryKey, data: T): void {
    entries.set(hash(key), { key, entry: { data, updatedAt: now() }, invalidated: false });
  }

  function isStale(key: QueryKey): boolean {
    const stored = entries.get(hash(key));
    return stored === undefined || stored.invalidated;
  }

  function invalidate(prefix: QueryKey): void {
    const stored = entries.get(hash(prefix));
    if (stored) stored.invalidated = true;
  }

  async function fetchQuery<T>(key: QueryKey, fetcher: () => Promise<T>): Promise<T> {
    const data = await fetcher();
    set(key, data);
    return data;
  }

  async function mutateOptimistic<T>(
    key: QueryKey,
    update: (old: T | undefined) => T,
    commit: () => Promise<void>,
  ): Promise<void> {
    set(key, update(get<T>(key)?.data));
    await commit();
  }

  return { get, set, isStale, invalidate, fetchQuery, mutateOptimistic };
}

export type QueryCache = ReturnType<typeof createQueryCache>;
