import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { settlementTotal } from '../../exercises/node/settlement-total.js';

const HEADER = 'payment_id,amount_minor,currency,status';
let dir: string;

beforeAll(async () => {
  dir = await mkdtemp(join(tmpdir(), 'sandpay-settlement-'));
});
afterAll(async () => {
  await rm(dir, { recursive: true, force: true });
});

async function fileWith(name: string, content: string): Promise<string> {
  const path = join(dir, name);
  await writeFile(path, content, 'utf8');
  return path;
}

describe('settlementTotal', { tags: ['@exercise'] }, () => {
  test('totals only SETTLED rows', async () => {
    const path = await fileWith(
      'basic.csv',
      [HEADER, 'pay_1001,1250,EUR,SETTLED', 'pay_1002,990,EUR,FAILED', 'pay_1003,4000,EUR,SETTLED', ''].join(
        '\n',
      ),
    );
    await expect(settlementTotal(path)).resolves.toEqual({
      currency: 'EUR',
      settledCount: 2,
      totalMinor: 5250,
    });
  });

  test('handles Windows line endings and no final newline', async () => {
    const path = await fileWith(
      'crlf.csv',
      [HEADER, 'pay_1,100,INR,SETTLED', 'pay_2,250,INR,SETTLED'].join('\r\n'),
    );
    await expect(settlementTotal(path)).resolves.toEqual({
      currency: 'INR',
      settledCount: 2,
      totalMinor: 350,
    });
  });

  test('a header-only file totals to zero', async () => {
    const path = await fileWith('empty.csv', `${HEADER}\n`);
    await expect(settlementTotal(path)).resolves.toEqual({ currency: '', settledCount: 0, totalMinor: 0 });
  });

  test('a missing file rejects with the fs error (ENOENT)', async () => {
    await expect(settlementTotal(join(dir, 'no-such-file.csv'))).rejects.toMatchObject({ code: 'ENOENT' });
  });

  test.each([
    ['decimal amount', 'pay_9,12.50,EUR,SETTLED'],
    ['negative amount', 'pay_9,-5,EUR,SETTLED'],
    ['text amount', 'pay_9,ten,EUR,SETTLED'],
    ['missing field', 'pay_9,1000,SETTLED'],
  ])('rejects a bad row (%s) and names its line', async (_label, row) => {
    const path = await fileWith('bad.csv', [HEADER, 'pay_1,100,EUR,SETTLED', row].join('\n'));
    await expect(settlementTotal(path)).rejects.toThrow(/line 3/);
  });

  test('rejects mixed currencies', async () => {
    const path = await fileWith(
      'mixed.csv',
      [HEADER, 'pay_1,100,EUR,SETTLED', 'pay_2,100,USD,FAILED'].join('\n'),
    );
    await expect(settlementTotal(path)).rejects.toThrow(/currency/);
  });

  test('sums large files exactly in integer minor units', async () => {
    const rows = Array.from({ length: 10_000 }, (_, i) => `pay_${i},${(i % 7) + 1},EUR,SETTLED`);
    const path = await fileWith('large.csv', [HEADER, ...rows].join('\n'));
    const expected = rows.reduce((sum, _row, i) => sum + (i % 7) + 1, 0);
    await expect(settlementTotal(path)).resolves.toEqual({
      currency: 'EUR',
      settledCount: 10_000,
      totalMinor: expected,
    });
  });
});
