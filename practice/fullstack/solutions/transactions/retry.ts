/**
 * Reference solution: retry a transaction that PostgreSQL aborted because of concurrency.
 * See the exercise file for the contract.
 */

export interface RetryOptions {
  maxAttempts?: number;
  backoffMs: (attempt: number) => number;
  sleep: (ms: number) => Promise<void>;
  onRetry?: (attempt: number, error: unknown) => void;
}

const RETRYABLE = new Set(['40001', '40P01']); // serialization_failure, deadlock_detected

export function isRetryable(error: unknown): boolean {
  if (typeof error !== 'object' || error === null || !('code' in error)) return false;
  const { code } = error as { code: unknown };
  return typeof code === 'string' && RETRYABLE.has(code);
}

export async function withTransactionRetry<T>(
  run: (attempt: number) => Promise<T>,
  options: RetryOptions,
): Promise<T> {
  const maxAttempts = options.maxAttempts ?? 3;
  for (let attempt = 1; ; attempt++) {
    try {
      return await run(attempt);
    } catch (error) {
      if (!isRetryable(error) || attempt >= maxAttempts) throw error;
      await options.sleep(options.backoffMs(attempt));
      options.onRetry?.(attempt, error);
    }
  }
}

export function exponentialBackoff(
  baseMs: number,
  capMs: number,
  random: () => number,
): (attempt: number) => number {
  return (attempt) => random() * Math.min(capMs, baseMs * 2 ** (attempt - 1));
}
