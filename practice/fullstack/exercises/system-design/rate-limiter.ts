// A per-merchant token-bucket rate limiter for the SandPay dashboard API, and the Express middleware that
// applies it. Implement createRateLimiter and rateLimit so that tests/system-design/rate-limiter.test.ts
// passes. The rules:
//   1. Every key (a merchant id) has its own bucket. A key seen for the first time starts with a FULL bucket
//      of `capacity` tokens.
//   2. Tokens flow in continuously at `refillPerSecond` (fractions count: 0.5 tokens after one second at
//      0.5/s) and a bucket never holds more than `capacity`. Use no timers - work out the refill from the
//      time elapsed since the bucket was last touched, read from options.now() (milliseconds).
//   3. take(key, cost = 1): if the bucket holds at least `cost` tokens, remove them and return
//      { allowed: true, remaining } where remaining is the whole tokens left (rounded down).
//   4. Otherwise return { allowed: false, remaining, retryAfterSeconds } and take NOTHING. retryAfterSeconds
//      is the whole number of seconds until `cost` tokens will be there (rounded up, never below 1).
//   5. A cost that is not a whole number from 1 to capacity throws a RangeError.
//   6. If the clock steps backwards, no tokens are added - and the time already counted is not counted
//      again when the clock catches up.
//   7. rateLimit(limiter, keyOf): middleware that takes one token from keyOf(req). Allowed: call next().
//      Refused: respond 429 with a Retry-After header (whole seconds) and an application/problem+json body
//      { title: 'Too Many Requests', status: 429, detail } - and do not call the route handler.
import type { Request, RequestHandler } from 'express';

export interface RateLimiterOptions {
  /** The most tokens a bucket holds - the largest burst a merchant can send at once. */
  capacity: number;
  /** Tokens added per second - the sustained rate. */
  refillPerSecond: number;
  /** The clock in milliseconds (Date.now in production, a fake clock in tests). */
  now: () => number;
}

export type TakeResult =
  { allowed: true; remaining: number } | { allowed: false; remaining: number; retryAfterSeconds: number };

export interface RateLimiter {
  /** Tries to take `cost` tokens (default 1) from the bucket for `key`. */
  take(key: string, cost?: number): TakeResult;
}

export function createRateLimiter(options: RateLimiterOptions): RateLimiter {
  return {
    take(key, cost = 1) {
      throw new Error(`TODO: take ${cost} token(s) for ${key} (capacity ${options.capacity})`);
    },
  };
}

export function rateLimit(limiter: RateLimiter, keyOf: (req: Request) => string): RequestHandler {
  return (req, _res, next) => {
    // TODO: take a token for keyOf(req) and answer 429 when it is refused.
    void limiter;
    void keyOf(req);
    next();
  };
}
