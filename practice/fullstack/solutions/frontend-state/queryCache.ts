// Reference solution (frontend-state-management): a tiny server-state cache - the ideas behind TanStack
// Query, SWR and RTK Query, without a library. Time comes from an injected clock, so tests are exact.

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
const startsWith = (key: QueryKey, prefix: QueryKey) => prefix.every((part, i) => key[i] === part);

export function createQueryCache({ now, staleTime }: QueryCacheOptions) {
  const entries = new Map<string, { key: QueryKey; entry: CacheEntry<unknown>; invalidated: boolean }>();
  const inFlight = new Map<string, Promise<unknown>>();

  function get<T>(key: QueryKey): CacheEntry<T> | undefined {
    return entries.get(hash(key))?.entry as CacheEntry<T> | undefined;
  }

  function set<T>(key: QueryKey, data: T): void {
    entries.set(hash(key), { key, entry: { data, updatedAt: now() }, invalidated: false });
  }

  /** Missing, invalidated, or older than staleTime. "Fresh until staleTime has elapsed." */
  function isStale(key: QueryKey): boolean {
    const stored = entries.get(hash(key));
    if (stored === undefined || stored.invalidated) return true;
    return now() - stored.entry.updatedAt >= staleTime;
  }

  /** Marks every entry whose key starts with `prefix` as stale. The data stays, to show while refetching. */
  function invalidate(prefix: QueryKey): void {
    for (const stored of entries.values()) if (startsWith(stored.key, prefix)) stored.invalidated = true;
  }

  /** Fresh data comes from the cache; otherwise one request per key, shared by every caller meanwhile. */
  function fetchQuery<T>(key: QueryKey, fetcher: () => Promise<T>): Promise<T> {
    const cached = get<T>(key);
    if (cached !== undefined && !isStale(key)) return Promise.resolve(cached.data);
    const id = hash(key);
    const pending = inFlight.get(id);
    if (pending !== undefined) return pending as Promise<T>;
    const request = fetcher()
      .then((data) => {
        set(key, data);
        return data;
      })
      .finally(() => inFlight.delete(id));
    inFlight.set(id, request);
    return request;
  }

  /**
   * Optimistic update: show `update(old)` at once, then run `commit` (the real request). On failure, put
   * the previous entry back exactly and rethrow; on success, invalidate the key so the server's truth is
   * fetched next time.
   */
  async function mutateOptimistic<T>(
    key: QueryKey,
    update: (old: T | undefined) => T,
    commit: () => Promise<void>,
  ): Promise<void> {
    const id = hash(key);
    const previous = entries.get(id);
    const snapshot = previous && { ...previous, entry: { ...previous.entry } };
    set(key, update(previous?.entry.data as T | undefined));
    try {
      await commit();
    } catch (error) {
      if (snapshot === undefined) entries.delete(id);
      else entries.set(id, snapshot);
      throw error;
    }
    invalidate(key);
  }

  return { get, set, isStale, invalidate, fetchQuery, mutateOptimistic };
}

export type QueryCache = ReturnType<typeof createQueryCache>;
