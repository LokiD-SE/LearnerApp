// Exercise: total a SandPay settlement file with node:fs/promises.
// Tests: tests/node/settlement-total.test.ts
//
// The file is CSV with a header line:
//
//   payment_id,amount_minor,currency,status
//   pay_1001,1250,EUR,SETTLED
//   pay_1002,990,EUR,FAILED
//
// amount_minor is an integer number of minor units (cents). Lines may end in \n or \r\n, and the
// file may end with an empty line.

export interface SettlementTotal {
  currency: string;
  /** How many SETTLED rows were counted. */
  settledCount: number;
  /** The sum of amount_minor over SETTLED rows. */
  totalMinor: number;
}

/**
 * Reads the file at `path` and totals its SETTLED rows.
 *
 * - Reject (throw from the async function) if the file can't be read - let the fs error through,
 *   so the caller can see its code (ENOENT for a missing file).
 * - Reject with an Error whose message contains "line <n>" (1-based, counting the header as line 1)
 *   if a row doesn't have four fields or its amount_minor is not a non-negative integer.
 * - Reject with an Error whose message contains "currency" if the rows don't all use one currency.
 * - A file with only the header totals to zero with currency "".
 */
export async function settlementTotal(path: string): Promise<SettlementTotal> {
  // TODO: read the file with readFile from 'node:fs/promises' and total the SETTLED rows.
  void path;
  return { currency: '', settledCount: 0, totalMinor: 0 };
}
