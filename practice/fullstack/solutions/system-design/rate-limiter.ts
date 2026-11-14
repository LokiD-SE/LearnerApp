// A per-merchant token-bucket rate limiter and the Express middleware that applies it - reference solution.
// No timers and no background work: each bucket is refilled lazily from the time elapsed since it was last
// touched, so the limiter costs nothing while a merchant is idle and is exact under a fake clock.
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

interface Bucket {
  tokens: number;
  updatedAt: number;
}

export function createRateLimiter(options: RateLimiterOptions): RateLimiter {
  const { capacity, refillPerSecond, now } = options;
  if (!Number.isSafeInteger(capacity) || capacity < 1)
    throw new RangeError('capacity must be a positive integer');
  if (!(refillPerSecond > 0) || !Number.isFinite(refillPerSecond)) {
    throw new RangeError('refillPerSecond must be a positive number');
  }
  const buckets = new Map<string, Bucket>();

  return {
    take(key, cost = 1) {
      if (!Number.isSafeInteger(cost) || cost < 1 || cost > capacity) {
        throw new RangeError(`cost must be a whole number from 1 to ${capacity}`);
      }
      const time = now();
      // A new key starts full; a known key gains what has flowed in since it was last touched.
      const bucket = buckets.get(key) ?? { tokens: capacity, updatedAt: time };
      // A clock that steps backwards (an NTP correction) adds nothing - and must not move updatedAt back,
      // or the same seconds would be counted twice later.
      const elapsedMs = Math.max(0, time - bucket.updatedAt);
      bucket.tokens = Math.min(capacity, bucket.tokens + (elapsedMs / 1000) * refillPerSecond);
      bucket.updatedAt = Math.max(bucket.updatedAt, time);
      buckets.set(key, bucket);

      if (bucket.tokens >= cost) {
        bucket.tokens -= cost;
        return { allowed: true, remaining: Math.floor(bucket.tokens) };
      }
      // Refused requests take nothing, so a client that keeps hammering still gets in once it waits.
      const missing = cost - bucket.tokens;
      return {
        allowed: false,
        remaining: Math.floor(bucket.tokens),
        retryAfterSeconds: Math.max(1, Math.ceil(missing / refillPerSecond)),
      };
    },
  };
}

/**
 * Express middleware: one token per request from the bucket named by `keyOf(req)`. A refused request gets
 * 429 Too Many Requests (RFC 6585 section 4) with Retry-After in whole seconds (RFC 9110 section 10.2.3)
 * and a problem details body (RFC 9457) - and never reaches the route handler.
 */
export function rateLimit(limiter: RateLimiter, keyOf: (req: Request) => string): RequestHandler {
  return (req, res, next) => {
    const result = limiter.take(keyOf(req));
    if (result.allowed) {
      next();
      return;
    }
    res
      .status(429)
      .set('Retry-After', String(result.retryAfterSeconds))
      .type('application/problem+json')
      .json({
        title: 'Too Many Requests',
        status: 429,
        detail: `Rate limit exceeded. Retry after ${result.retryAfterSeconds} seconds.`,
      });
  };
}
