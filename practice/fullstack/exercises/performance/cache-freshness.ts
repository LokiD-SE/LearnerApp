// Exercise: decide, like an HTTP cache, whether a stored response can be reused - RFC 9111
// (HTTP Caching) sections 4.2 and 5.2, and the stale-while-revalidate extension of RFC 5861.
// Tests: tests/performance/cache-freshness.test.ts
//
// All times are whole seconds since the Unix epoch, like `Math.floor(Date.now() / 1000)`.

/** Cache-Control directives: lower-case name -> argument (quotes removed), or `true` if it has none. */
export type Directives = Map<string, string | true>;

/** A response held in a cache, with the clock values RFC 9111 section 4.2.3 needs. */
export interface StoredResponse {
  /** Response header fields with lower-case names: cache-control, expires, date, age, last-modified. */
  headers: Record<string, string>;
  /** The clock when the request that produced this response was sent. */
  requestTime: number;
  /** The clock when the response was received. */
  responseTime: number;
}

/**
 * What the cache does with the stored response for a new request.
 * - `do-not-store` - it must not have been stored at all (no-store, or private in a shared cache);
 * - `reuse` - fresh: answer from the cache without contacting the origin;
 * - `reuse-and-revalidate` - stale, but inside its stale-while-revalidate window: answer from the
 *   cache now and revalidate in the background;
 * - `validate` - send a conditional request to the origin before using it.
 */
export type Decision = 'do-not-store' | 'reuse' | 'reuse-and-revalidate' | 'validate';

/** Parses an HTTP-date (for example `Sat, 14 Nov 2026 07:49:38 GMT`) to seconds, or undefined. */
export function parseHttpDate(value: string | undefined): number | undefined {
  if (value === undefined) return undefined;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? undefined : Math.floor(ms / 1000);
}

/** A delta-seconds value (RFC 9111 section 1.2.2): one or more digits, nothing else. */
function deltaSeconds(value: string | true | undefined): number | undefined {
  return typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : undefined;
}

/**
 * Parses a Cache-Control field value (RFC 9111 section 5.2).
 * - Directive names are case-insensitive: store them in lower case.
 * - An argument may be a token (`max-age=60`) or a quoted string (`max-age="60"`, `no-cache="Set-Cookie"`):
 *   store it without the quotes. A comma inside a quoted string does not end the directive.
 * - If a directive appears twice, keep the first occurrence (section 4.2.1).
 * - Ignore empty members (`max-age=60, , public`).
 */
export function parseCacheControl(value: string | undefined): Directives {
  // TODO: split on commas outside quotes, lower-case the names, unquote arguments, keep first occurrences.
  void value;
  return new Map();
}

/**
 * The explicit freshness lifetime in seconds (RFC 9111 section 4.2.1), using the FIRST rule that applies:
 * 1. a shared cache and `s-maxage` present -> its value;
 * 2. `max-age` present -> its value;
 * 3. `Expires` present -> Expires minus Date (use `responseTime` when there is no Date), never below 0;
 * 4. otherwise `undefined` - there is no explicit expiration time.
 * An invalid value (`max-age=ten`, `Expires: 0`) means "already stale": return 0.
 */
export function freshnessLifetime(response: StoredResponse, shared: boolean): number | undefined {
  // TODO: s-maxage (shared only), then max-age, then Expires minus Date - the first rule that applies.
  void response;
  void shared;
  void deltaSeconds;
  return undefined;
}

/**
 * The current age in seconds (RFC 9111 section 4.2.3):
 *   apparent_age = max(0, response_time - date_value)        (date_value = response_time if no Date)
 *   corrected_age_value = age_value + (response_time - request_time)
 *   corrected_initial_age = max(apparent_age, corrected_age_value)
 *   current_age = corrected_initial_age + (now - response_time)
 * `age_value` is the Age header - its first member if it is a list - or 0 if it is missing or not a
 * non-negative integer (section 5.1).
 */
export function currentAge(response: StoredResponse, now: number): number {
  // TODO: apparent_age, corrected_age_value, corrected_initial_age, then add the resident time.
  void response;
  void now;
  return 0;
}

/**
 * Decides what to do with a stored response, checking in this order:
 * 1. `no-store`, or `private` in a shared cache -> `do-not-store`;
 * 2. `no-cache` (with or without an argument - most caches treat both alike) -> `validate`;
 * 3. the lifetime is the explicit one; without one, a heuristic of 10% of (Date - Last-Modified),
 *    rounded down, when both are present (RFC 9111 section 4.2.2 mentions 10% as "a typical
 *    setting"); otherwise 0;
 * 4. fresh (lifetime > current age) -> `reuse`;
 * 5. stale and `must-revalidate`, or stale in a shared cache with `proxy-revalidate` or `s-maxage`
 *    -> `validate` (section 4.2.4: these forbid serving stale);
 * 6. stale by no more than `stale-while-revalidate` seconds (RFC 5861) -> `reuse-and-revalidate`;
 * 7. otherwise -> `validate`.
 */
export function decide(response: StoredResponse, now: number, shared: boolean): Decision {
  // TODO: follow the seven steps above, in order.
  void response;
  void now;
  void shared;
  return 'validate';
}
