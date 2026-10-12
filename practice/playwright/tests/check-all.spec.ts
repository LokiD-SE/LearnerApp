import { expect, test } from '@playwright/test';
import { checkAll } from '../exercises/async/check-all.js';

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
const ok = (name: string, ms: number) => ({ name, run: () => wait(ms) });
const failing = (name: string, ms: number, message: string) => ({
  name,
  run: async () => {
    await wait(ms);
    throw new Error(message);
  },
});

test.describe('checkAll', { tag: '@exercise' }, () => {
  test('reports passed and failed checks in the order given', async () => {
    const summary = await checkAll([
      ok('api', 120),
      failing('payment', 10, 'sandbox unreachable'),
      ok('webhook', 60),
    ]);
    expect(summary).toEqual({
      passed: ['api', 'webhook'],
      failed: [{ name: 'payment', message: 'sandbox unreachable' }],
    });
  });

  test('waits for every check before it resolves', async () => {
    let finished = false;
    await checkAll([{ name: 'slow', run: () => wait(150).then(() => void (finished = true)) }]);
    expect(finished).toBe(true);
  });

  test('runs the checks at the same time', async () => {
    const start = Date.now();
    const summary = await checkAll(Array.from({ length: 5 }, (_, i) => ok(`check-${i}`, 200)));
    expect(summary.passed).toHaveLength(5);
    expect(Date.now() - start, 'five 200 ms checks one after another would take 1000 ms').toBeLessThan(600);
  });

  test('an empty list is an empty summary', async () => {
    expect(await checkAll([])).toEqual({ passed: [], failed: [] });
  });
});
