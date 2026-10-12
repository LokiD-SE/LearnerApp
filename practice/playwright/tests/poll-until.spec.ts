import { expect, test } from '@playwright/test';
import { pollUntil } from '../exercises/async/poll-until';

/** A status that is PENDING for the first `pendingCalls` reads, then SUCCEEDED. */
function statusSource(pendingCalls: number) {
  let calls = 0;
  return {
    get calls() {
      return calls;
    },
    read: async () => (++calls > pendingCalls ? 'SUCCEEDED' : 'PENDING'),
  };
}

test.describe('pollUntil', { tag: '@exercise' }, () => {
  test('asks again until the value is done', async () => {
    const source = statusSource(3);
    const value = await pollUntil(source.read, (s) => s === 'SUCCEEDED', { timeout: 2_000, interval: 20 });
    expect(value).toBe('SUCCEEDED');
    expect(source.calls).toBe(4);
  });

  test('resolves at once when the first value is done', async () => {
    const start = Date.now();
    await pollUntil(statusSource(0).read, (s) => s === 'SUCCEEDED', { timeout: 5_000, interval: 500 });
    expect(Date.now() - start).toBeLessThan(200);
  });

  test('rejects with the last value when time runs out', async () => {
    const start = Date.now();
    await expect(
      pollUntil(statusSource(1_000).read, (s) => s === 'SUCCEEDED', { timeout: 300, interval: 50 }),
    ).rejects.toThrow(/timed out.*PENDING/);
    expect(Date.now() - start).toBeLessThan(1_000);
  });

  test('never overlaps calls', async () => {
    let running = 0;
    let maxRunning = 0;
    let calls = 0;
    const slowRead = async () => {
      running += 1;
      maxRunning = Math.max(maxRunning, running);
      await new Promise((resolve) => setTimeout(resolve, 60));
      running -= 1;
      return ++calls;
    };
    expect(await pollUntil(slowRead, (n) => n >= 3, { timeout: 2_000, interval: 1 })).toBe(3);
    expect(maxRunning).toBe(1);
  });
});
