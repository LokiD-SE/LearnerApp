// Reference solution for exercises/node/settlement-total.ts.
import { readFile } from 'node:fs/promises';

export interface SettlementTotal {
  currency: string;
  /** How many SETTLED rows were counted. */
  settledCount: number;
  /** The sum of amount_minor over SETTLED rows. */
  totalMinor: number;
}

export async function settlementTotal(path: string): Promise<SettlementTotal> {
  // No try/catch: a read error (ENOENT, EACCES) rejects this promise with the original error.
  const text = await readFile(path, 'utf8');
  const lines = text.split(/\r?\n/);

  let currency = '';
  let settledCount = 0;
  let totalMinor = 0;

  // Line 1 is the header; numbering stays 1-based so messages match what an editor shows.
  for (let index = 1; index < lines.length; index += 1) {
    const line = lines[index] ?? '';
    const lineNumber = index + 1;
    if (line.trim() === '') continue;

    const fields = line.split(',');
    if (fields.length !== 4) throw new Error(`line ${lineNumber}: expected 4 fields, got ${fields.length}`);
    const [, amount = '', rowCurrency = '', status = ''] = fields;

    if (!/^\d+$/.test(amount))
      throw new Error(`line ${lineNumber}: amount_minor must be a non-negative integer, got "${amount}"`);
    if (currency === '') currency = rowCurrency;
    else if (rowCurrency !== currency)
      throw new Error(`line ${lineNumber}: currency ${rowCurrency} differs from ${currency}`);

    if (status === 'SETTLED') {
      settledCount += 1;
      totalMinor += Number(amount);
    }
  }
  return { currency, settledCount, totalMinor };
}
