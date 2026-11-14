import express from 'express';
import request from 'supertest';
import {
  createRateLimiter,
  rateLimit,
  type RateLimiter,
} from '../../exercises/system-design/rate-limiter.js';

const START = Date.UTC(2026, 10, 14, 9, 0, 0);

/** A fake clock the tests move by hand - no real waiting, no flaky timing. */
function fakeClock() {
  let now = START;
  return { now: () => now, advance: (ms: number) => (now += ms), set: (ms: number) => (now = ms) };
}

function drain(limiter: RateLimiter, key: string, times: number): void {
  for (let i = 0; i < times; i++)
    expect(limiter.take(key).allowed, `request ${i + 1} of the burst`).toBe(true);
}

describe('token-bucket rate limiter', { tags: ['@exercise'] }, () => {
  test('a new merchant gets a full bucket, then is refused with Retry-After', () => {
    const clock = fakeClock();
    const limiter = createRateLimiter({ capacity: 5, refillPerSecond: 0.5, now: clock.now });
    const remaining = Array.from({ length: 5 }, () => limiter.take('mer_1001'));
    expect(remaining).toEqual([4, 3, 2, 1, 0].map((r) => ({ allowed: true, remaining: r })));
    expect(limiter.take('mer_1001')).toEqual({ allowed: false, remaining: 0, retryAfterSeconds: 2 });
  });

  test('tokens refill continuously, including fractions', () => {
    const clock = fakeClock();
    const limiter = createRateLimiter({ capacity: 5, refillPerSecond: 0.5, now: clock.now });
    drain(limiter, 'mer_1001', 5);
    clock.advance(1000); // half a token
    expect(limiter.take('mer_1001')).toEqual({ allowed: false, remaining: 0, retryAfterSeconds: 1 });
    clock.advance(1000); // a whole token
    expect(limiter.take('mer_1001')).toEqual({ allowed: true, remaining: 0 });
  });

  test('a refill lands exactly on time, not early', () => {
    const clock = fakeClock();
    const limiter = createRateLimiter({ capacity: 1, refillPerSecond: 4, now: clock.now });
    drain(limiter, 'mer_1001', 1);
    clock.advance(249);
    expect(limiter.take('mer_1001').allowed, '249 ms at 4 tokens/s is not yet a token').toBe(false);
    clock.advance(1);
    expect(limiter.take('mer_1001').allowed, '250 ms at 4 tokens/s is one token').toBe(true);
  });

  test('a bucket never holds more than its capacity', () => {
    const clock = fakeClock();
    const limiter = createRateLimiter({ capacity: 3, refillPerSecond: 1, now: clock.now });
    drain(limiter, 'mer_1001', 1);
    clock.advance(60 * 60 * 1000); // an hour idle
    drain(limiter, 'mer_1001', 3);
    expect(limiter.take('mer_1001').allowed, 'the fourth request after an idle hour').toBe(false);
  });

  test('refused requests take nothing, so a client that keeps retrying still gets in', () => {
    const clock = fakeClock();
    const limiter = createRateLimiter({ capacity: 2, refillPerSecond: 1, now: clock.now });
    drain(limiter, 'mer_1001', 2);
    for (let i = 0; i < 50; i++) {
      clock.advance(10);
      expect(limiter.take('mer_1001').allowed).toBe(false);
    }
    clock.advance(500); // 50 x 10 ms + 500 ms = one second since the bucket emptied
    expect(limiter.take('mer_1001')).toEqual({ allowed: true, remaining: 0 });
  });

  test('Retry-After is whole seconds rounded up, and at least 1', () => {
    const clock = fakeClock();
    const fast = createRateLimiter({ capacity: 1, refillPerSecond: 10, now: clock.now });
    drain(fast, 'mer_1001', 1);
    expect(fast.take('mer_1001')).toEqual({ allowed: false, remaining: 0, retryAfterSeconds: 1 });
    const slow = createRateLimiter({ capacity: 10, refillPerSecond: 0.25, now: clock.now });
    drain(slow, 'mer_1001', 10);
    clock.advance(1000); // 0.25 tokens there; the missing 2.75 need 11 s
    expect(slow.take('mer_1001', 3)).toEqual({ allowed: false, remaining: 0, retryAfterSeconds: 11 });
  });

  test('a request can cost several tokens', () => {
    const clock = fakeClock();
    const limiter = createRateLimiter({ capacity: 10, refillPerSecond: 1, now: clock.now });
    expect(limiter.take('mer_1001', 6)).toEqual({ allowed: true, remaining: 4 });
    expect(limiter.take('mer_1001', 6)).toEqual({ allowed: false, remaining: 4, retryAfterSeconds: 2 });
    expect(limiter.take('mer_1001', 4)).toEqual({ allowed: true, remaining: 0 });
  });

  test('a cost outside 1..capacity, or not whole, is a RangeError', () => {
    const limiter = createRateLimiter({ capacity: 5, refillPerSecond: 1, now: fakeClock().now });
    for (const cost of [0, -1, 1.5, 6, Number.NaN]) {
      expect(() => limiter.take('mer_1001', cost), `cost ${cost}`).toThrow(RangeError);
    }
  });

  test('each merchant has its own bucket', () => {
    const clock = fakeClock();
    const limiter = createRateLimiter({ capacity: 2, refillPerSecond: 1, now: clock.now });
    drain(limiter, 'mer_1001', 2);
    expect(limiter.take('mer_1001').allowed).toBe(false);
    expect(limiter.take('mer_2002')).toEqual({ allowed: true, remaining: 1 });
  });

  test('a clock that steps backwards adds nothing and is not counted twice', () => {
    const clock = fakeClock();
    const limiter = createRateLimiter({ capacity: 5, refillPerSecond: 0.5, now: clock.now });
    drain(limiter, 'mer_1001', 5);
    clock.set(START - 10_000); // an NTP step back of 10 s
    expect(limiter.take('mer_1001').allowed, 'no tokens appear when time goes backwards').toBe(false);
    clock.set(START + 2000); // two real seconds after the bucket emptied: one token
    expect(limiter.take('mer_1001')).toEqual({ allowed: true, remaining: 0 });
  });
});

describe('rate limit middleware', { tags: ['@exercise'] }, () => {
  function app() {
    const clock = fakeClock();
    const limiter = createRateLimiter({ capacity: 2, refillPerSecond: 1, now: clock.now });
    const handled: string[] = [];
    const server = express();
    server.use(rateLimit(limiter, (req) => req.get('x-merchant-id') ?? 'anonymous'));
    server.get('/v1/payments', (req, res) => {
      handled.push(req.get('x-merchant-id') ?? 'anonymous');
      res.json({ data: [] });
    });
    return { server, clock, handled };
  }

  test('requests within the limit reach the handler', async () => {
    const { server, handled } = app();
    for (let i = 0; i < 2; i++)
      await request(server).get('/v1/payments').set('X-Merchant-Id', 'mer_1001').expect(200);
    expect(handled).toEqual(['mer_1001', 'mer_1001']);
  });

  test('a refused request gets 429, Retry-After and problem details - and never reaches the handler', async () => {
    const { server, handled } = app();
    for (let i = 0; i < 2; i++) await request(server).get('/v1/payments').set('X-Merchant-Id', 'mer_1001');
    const res = await request(server).get('/v1/payments').set('X-Merchant-Id', 'mer_1001');
    expect(res.status).toBe(429);
    expect(res.headers['retry-after']).toBe('1');
    expect(res.headers['content-type']).toMatch(/^application\/problem\+json/);
    expect(res.body).toMatchObject({ title: 'Too Many Requests', status: 429 });
    expect(typeof res.body.detail).toBe('string');
    expect(handled).toHaveLength(2);
  });

  test('one merchant hitting the limit does not block another, and waiting lets it back in', async () => {
    const { server, clock } = app();
    for (let i = 0; i < 3; i++) await request(server).get('/v1/payments').set('X-Merchant-Id', 'mer_1001');
    await request(server).get('/v1/payments').set('X-Merchant-Id', 'mer_2002').expect(200);
    clock.advance(1000);
    await request(server).get('/v1/payments').set('X-Merchant-Id', 'mer_1001').expect(200);
  });
});
