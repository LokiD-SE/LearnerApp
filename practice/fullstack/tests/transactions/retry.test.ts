import { PGlite } from '@electric-sql/pglite';
import { exponentialBackoff, isRetryable, withTransactionRetry } from '../../exercises/transactions/retry.js';

/** An error shaped like the ones node-postgres and PGlite throw: the SQLSTATE is in `code`. */
function pgError(code: string, message: string): Error & { code: string } {
  return Object.assign(new Error(message), { code });
}
const serializationFailure = () =>
  pgError('40001', 'could not serialize access due to read/write dependencies among transactions');
const deadlock = () => pgError('40P01', 'deadlock detected');

function options(extra: Partial<Parameters<typeof withTransactionRetry>[1]> = {}) {
  const sleeps: number[] = [];
  return {
    sleeps,
    opts: {
      backoffMs: (attempt: number) => attempt * 10,
      sleep: async (ms: number) => {
        sleeps.push(ms);
      },
      ...extra,
    },
  };
}

describe('retrying serialization failures and deadlocks', { tags: ['@exercise'] }, () => {
  test('isRetryable: only SQLSTATE 40001 and 40P01', () => {
    expect(isRetryable(serializationFailure())).toBe(true);
    expect(isRetryable(deadlock())).toBe(true);
    expect(isRetryable({ code: '40001' })).toBe(true);
    expect(isRetryable(pgError('23514', 'violates check constraint'))).toBe(false);
    expect(isRetryable(pgError('23505', 'duplicate key value'))).toBe(false);
    expect(isRetryable(new Error('connection reset'))).toBe(false);
    expect(isRetryable({ code: 40001 })).toBe(false);
    expect(isRetryable('40001')).toBe(false);
    expect(isRetryable(null)).toBe(false);
    expect(isRetryable(undefined)).toBe(false);
  });

  test('a real constraint violation from PostgreSQL is not retryable', async () => {
    const db = new PGlite();
    await db.exec('CREATE TABLE t (n int CHECK (n >= 0))');
    const error = await db.query('INSERT INTO t VALUES (-1)').catch((e: unknown) => e);
    expect((error as { code: string }).code).toBe('23514');
    expect(isRetryable(error)).toBe(false);
  });

  test('success on the first attempt returns the value without sleeping', async () => {
    const { sleeps, opts } = options();
    const run = vi.fn(async () => 'committed');
    expect(await withTransactionRetry(run, opts)).toBe('committed');
    expect(run).toHaveBeenCalledTimes(1);
    expect(sleeps).toEqual([]);
  });

  test('runs the whole function again after a serialization failure or a deadlock', async () => {
    const { sleeps, opts } = options();
    const failures = [serializationFailure(), deadlock()];
    const attempts: number[] = [];
    const result = await withTransactionRetry(async (attempt) => {
      attempts.push(attempt);
      const failure = failures.shift();
      if (failure) throw failure;
      return `done on attempt ${attempt}`;
    }, opts);
    expect(result).toBe('done on attempt 3');
    expect(attempts).toEqual([1, 2, 3]);
    expect(sleeps).toEqual([10, 20]);
  });

  test('sleeps before each retry and reports it', async () => {
    const order: string[] = [];
    const failure = serializationFailure();
    await withTransactionRetry(
      async (attempt) => {
        order.push(`run ${attempt}`);
        if (attempt === 1) throw failure;
        return 'ok';
      },
      {
        backoffMs: () => 25,
        sleep: async (ms) => {
          order.push(`sleep ${ms}`);
        },
        onRetry: (attempt, error) => {
          order.push(`retry after ${attempt}: ${(error as Error).message.slice(0, 13)}`);
        },
      },
    );
    expect(order).toEqual(['run 1', 'sleep 25', 'retry after 1: could not ser', 'run 2']);
  });

  test('a non-retryable error is rethrown at once, unchanged', async () => {
    const { sleeps, opts } = options();
    const violation = pgError('23514', 'new row violates check constraint');
    const run = vi.fn(async () => {
      throw violation;
    });
    await expect(withTransactionRetry(run, opts)).rejects.toBe(violation);
    expect(run).toHaveBeenCalledTimes(1);
    expect(sleeps).toEqual([]);
  });

  test('gives up after maxAttempts (default 3) and rethrows the last error', async () => {
    const { sleeps, opts } = options();
    const errors = [serializationFailure(), serializationFailure(), serializationFailure()];
    let i = 0;
    const run = vi.fn(async () => {
      throw errors[i++];
    });
    await expect(withTransactionRetry(run, opts)).rejects.toBe(errors[2]);
    expect(run).toHaveBeenCalledTimes(3);
    expect(sleeps).toEqual([10, 20]);
  });

  test('maxAttempts can be changed', async () => {
    const { opts } = options({ maxAttempts: 5 });
    const run = vi.fn(async () => {
      throw deadlock();
    });
    await expect(withTransactionRetry(run, opts)).rejects.toMatchObject({ code: '40P01' });
    expect(run).toHaveBeenCalledTimes(5);
  });

  test('exponentialBackoff: full jitter under a doubling cap', () => {
    const atMax = exponentialBackoff(50, 1000, () => 0.999);
    expect(Math.round(atMax(1))).toBe(50);
    expect(Math.round(atMax(2))).toBe(100);
    expect(Math.round(atMax(3))).toBe(200);
    expect(Math.round(atMax(5))).toBe(799);
    expect(Math.round(atMax(6))).toBe(999);
    expect(Math.round(atMax(20))).toBe(999);
    const half = exponentialBackoff(50, 1000, () => 0.5);
    expect(half(3)).toBe(100);
    expect(exponentialBackoff(50, 1000, () => 0)(4)).toBe(0);
  });
});
