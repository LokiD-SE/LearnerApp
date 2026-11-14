/**
 * Exercise: retry a transaction that PostgreSQL aborted because of concurrency.
 *
 * At Repeatable Read and Serializable, PostgreSQL may abort a transaction with SQLSTATE 40001
 * (serialization_failure); at any level two transactions can deadlock, and one gets 40P01
 * (deadlock_detected). The manual says the application must then retry the WHOLE transaction -
 * including the reads and the decisions made from them. PostgreSQL never retries for you.
 *
 * Implement:
 *
 * - `isRetryable(error)`: true only for an error object whose `code` is '40001' or '40P01'.
 *   Anything else (a constraint violation such as '23514', a syntax error, a plain Error,
 *   a string, null) is not retryable.
 * - `withTransactionRetry(run, options)`: call `run(attempt)` (attempt counts from 1).
 *     - If it resolves, return its value.
 *     - If it rejects with a retryable error and attempts are left, wait
 *       `await options.sleep(options.backoffMs(attempt))`, call `options.onRetry?.(attempt, error)`,
 *       then call `run` again - the whole function, from the start.
 *     - Rethrow a non-retryable error at once, unchanged.
 *     - After `maxAttempts` attempts (default 3) rethrow the last error, unchanged.
 * - `exponentialBackoff(baseMs, capMs, random)`: returns a function of the attempt number that
 *   gives a random delay in [0, min(capMs, baseMs * 2 ** (attempt - 1))) - "full jitter", so
 *   clients that collided once don't collide again in lock step. `random` is injected
 *   (Math.random in production) so the tests are deterministic.
 */

export interface RetryOptions {
  maxAttempts?: number;
  backoffMs: (attempt: number) => number;
  sleep: (ms: number) => Promise<void>;
  onRetry?: (attempt: number, error: unknown) => void;
}

export function isRetryable(error: unknown): boolean {
  return error instanceof Error;
}

export async function withTransactionRetry<T>(
  run: (attempt: number) => Promise<T>,
  options: RetryOptions,
): Promise<T> {
  void options;
  return run(1);
}

export function exponentialBackoff(
  baseMs: number,
  capMs: number,
  random: () => number,
): (attempt: number) => number {
  return () => baseMs * random() + capMs * 0;
}
