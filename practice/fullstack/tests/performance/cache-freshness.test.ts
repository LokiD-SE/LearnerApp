import {
  currentAge,
  decide,
  freshnessLifetime,
  parseCacheControl,
  type StoredResponse,
} from '../../exercises/performance/cache-freshness.js';

/** 14 Nov 2026 07:49:38 GMT, in seconds - the Date of the real response captured in the lesson. */
const T = Date.UTC(2026, 10, 14, 7, 49, 38) / 1000;
const httpDate = (seconds: number) => new Date(seconds * 1000).toUTCString();

/** A response requested at T - 1, generated at T and received at T (no Age header, no clock skew). */
function stored(headers: Record<string, string>, overrides: Partial<StoredResponse> = {}): StoredResponse {
  return { headers: { date: httpDate(T), ...headers }, requestTime: T - 1, responseTime: T, ...overrides };
}

describe('parseCacheControl', { tags: ['@exercise'] }, () => {
  test('reads directives with and without arguments', () => {
    const d = parseCacheControl('public, max-age=31536000, immutable');
    expect([...d.entries()]).toEqual([
      ['public', true],
      ['max-age', '31536000'],
      ['immutable', true],
    ]);
  });

  test('names are case-insensitive and stored in lower case; spaces and empty members are ignored', () => {
    const d = parseCacheControl('  Max-Age=60 , , NO-CACHE');
    expect(d.get('max-age')).toBe('60');
    expect(d.get('no-cache')).toBe(true);
    expect(d.size).toBe(2);
  });

  test('accepts quoted arguments, including a comma inside the quotes', () => {
    const d = parseCacheControl('private="Set-Cookie, X-Session", max-age="5"');
    expect(d.get('private')).toBe('Set-Cookie, X-Session');
    expect(d.get('max-age')).toBe('5');
  });

  test('keeps the first occurrence of a repeated directive', () => {
    expect(parseCacheControl('max-age=60, max-age=3600').get('max-age')).toBe('60');
  });

  test('a missing header gives no directives', () => {
    expect(parseCacheControl(undefined).size).toBe(0);
  });
});

describe('freshnessLifetime', { tags: ['@exercise'] }, () => {
  test('max-age gives the lifetime', () => {
    expect(freshnessLifetime(stored({ 'cache-control': 'max-age=600' }), false)).toBe(600);
  });

  test('s-maxage wins in a shared cache only', () => {
    const r = stored({ 'cache-control': 'max-age=60, s-maxage=3600' });
    expect(freshnessLifetime(r, true)).toBe(3600);
    expect(freshnessLifetime(r, false)).toBe(60);
  });

  test('max-age wins over Expires', () => {
    const r = stored({ 'cache-control': 'max-age=60', expires: httpDate(T + 86400) });
    expect(freshnessLifetime(r, false)).toBe(60);
  });

  test('Expires minus Date, or minus the receive time when there is no Date', () => {
    expect(freshnessLifetime(stored({ expires: httpDate(T + 300) }), false)).toBe(300);
    const noDate: StoredResponse = {
      headers: { expires: httpDate(T + 120) },
      requestTime: T - 1,
      responseTime: T,
    };
    expect(freshnessLifetime(noDate, false)).toBe(120);
  });

  test('invalid values mean already stale', () => {
    expect(freshnessLifetime(stored({ 'cache-control': 'max-age=ten' }), false)).toBe(0);
    expect(freshnessLifetime(stored({ expires: '0' }), false)).toBe(0);
    expect(freshnessLifetime(stored({ expires: httpDate(T - 60) }), false)).toBe(0);
  });

  test('no explicit expiration gives undefined', () => {
    expect(freshnessLifetime(stored({ 'cache-control': 'public' }), false)).toBeUndefined();
  });
});

describe('currentAge', { tags: ['@exercise'] }, () => {
  test('without an Age header: the response delay plus the time it has been stored', () => {
    // corrected_age_value = 0 + (T - (T - 1)) = 1; resident 99 seconds
    expect(currentAge(stored({}), T + 99)).toBe(100);
  });

  test('adds the Age a CDN reported', () => {
    expect(currentAge(stored({ age: '250' }), T + 10)).toBe(261);
  });

  test('uses apparent_age when the Date is older than the corrected Age', () => {
    // generated 40 s before it was received, no Age header: apparent_age 40 > corrected 1
    expect(currentAge(stored({ date: httpDate(T - 40) }), T)).toBe(40);
  });

  test('a Date in the future (clock skew) never makes the age negative', () => {
    expect(currentAge(stored({ date: httpDate(T + 500) }), T)).toBe(1);
  });

  test('uses the first member of a list and ignores an invalid Age', () => {
    expect(currentAge(stored({ age: '30, 900' }), T)).toBe(31);
    expect(currentAge(stored({ age: '-5' }), T)).toBe(1);
  });
});

describe('decide', { tags: ['@exercise'] }, () => {
  test('a hashed asset is reused for a year', () => {
    const r = stored({ 'cache-control': 'public, max-age=31536000, immutable' });
    expect(decide(r, T + 86400 * 300, false)).toBe('reuse');
  });

  test('the freshness boundary: fresh only while the lifetime is greater than the age', () => {
    const r = stored({ 'cache-control': 'max-age=600' }); // age at T is 1
    expect(decide(r, T + 598, false)).toBe('reuse'); // age 599
    expect(decide(r, T + 599, false)).toBe('validate'); // age 600
  });

  test('no-cache always validates, even when fresh', () => {
    expect(decide(stored({ 'cache-control': 'no-cache' }), T, false)).toBe('validate');
    expect(decide(stored({ 'cache-control': 'max-age=600, no-cache' }), T, false)).toBe('validate');
  });

  test('no-store, and private in a shared cache, are never stored', () => {
    expect(decide(stored({ 'cache-control': 'no-store, max-age=600' }), T, false)).toBe('do-not-store');
    const priv = stored({ 'cache-control': 'private, max-age=600' });
    expect(decide(priv, T, true)).toBe('do-not-store');
    expect(decide(priv, T, false)).toBe('reuse');
  });

  test('stale-while-revalidate: served stale inside the window, validated after it (RFC 5861 example)', () => {
    const r = stored({ 'cache-control': 'max-age=600, stale-while-revalidate=30' });
    expect(decide(r, T + 620, false)).toBe('reuse-and-revalidate'); // age 621, 21 s stale
    expect(decide(r, T + 629, false)).toBe('reuse-and-revalidate'); // 30 s stale
    expect(decide(r, T + 630, false)).toBe('validate'); // 31 s stale
  });

  test('must-revalidate forbids serving stale; s-maxage forbids it in a shared cache', () => {
    const must = stored({ 'cache-control': 'max-age=60, must-revalidate, stale-while-revalidate=600' });
    expect(decide(must, T + 120, false)).toBe('validate');
    const s = stored({ 'cache-control': 's-maxage=60, stale-while-revalidate=600' });
    expect(decide(s, T + 120, true)).toBe('validate');
    const proxy = stored({ 'cache-control': 'max-age=60, proxy-revalidate, stale-while-revalidate=600' });
    expect(decide(proxy, T + 120, true)).toBe('validate');
    expect(decide(proxy, T + 120, false)).toBe('reuse-and-revalidate');
  });

  test('heuristic freshness: 10% of the time since Last-Modified, only without explicit expiry', () => {
    const r = stored({ 'last-modified': httpDate(T - 10000) }); // heuristic lifetime 1000
    expect(decide(r, T + 998, false)).toBe('reuse'); // age 999
    expect(decide(r, T + 999, false)).toBe('validate'); // age 1000
    const explicit = stored({ 'last-modified': httpDate(T - 10000), 'cache-control': 'max-age=0' });
    expect(decide(explicit, T, false)).toBe('validate');
  });

  test('no freshness information and no Last-Modified: validate', () => {
    expect(decide(stored({}), T, false)).toBe('validate');
  });
});
