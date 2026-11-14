// Runs the queries in exercises/sql/reports.ts against a small SandPay data set in PGlite
// (PostgreSQL 18 compiled to WebAssembly) and checks every row they return.
import { PGlite } from '@electric-sql/pglite';
import {
  dailyRevenue,
  netPaidOrders,
  paidOrdersWithoutRefunds,
  revenueByMerchant,
} from '../../exercises/sql/reports.js';

// A schema written for this test, so this exercise doesn't depend on the schema exercise.
// refunds.order_id is nullable here: refunds the processor reported that aren't matched to an order yet.
const SCHEMA = `
  CREATE TABLE merchants (id bigint PRIMARY KEY, name text NOT NULL);
  CREATE TABLE orders (
    id bigint PRIMARY KEY,
    merchant_id bigint NOT NULL REFERENCES merchants (id),
    amount_minor bigint NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL
  );
  CREATE TABLE refunds (id bigint PRIMARY KEY, order_id bigint REFERENCES orders (id), amount_minor bigint NOT NULL);

  INSERT INTO merchants VALUES (1, 'Lumen Books'), (2, 'Kettle & Co'), (3, 'Quiet Cafe'), (4, 'Atlas Maps');
  INSERT INTO orders VALUES
    (101, 1, 2599, 'PAID',    '2026-11-10 09:15+00'),
    (102, 1, 1250, 'PAID',    '2026-11-10 23:59+00'),
    (103, 1, 4000, 'FAILED',  '2026-11-11 08:40+00'),
    (104, 1,  700, 'PAID',    '2026-11-13 00:00+00'),
    (105, 2,  990, 'PAID',    '2026-11-11 10:05+00'),
    (106, 2, 3100, 'PENDING', '2026-11-12 16:30+00'),
    (107, 4, 4549, 'PAID',    '2026-11-12 12:00+00'),
    (108, 1,  300, 'PAID',    '2026-11-11 00:30+05:30');
  INSERT INTO refunds VALUES (1, 101, 599), (2, 105, 990), (3, 101, 1000), (4, NULL, 250);
`;

let db: PGlite;

type Row = Record<string, unknown>;
// Counts and sums come back as numbers, bigints or numeric strings depending on their SQL type
// (sum of a bigint column is numeric), so compare values: every column except name and day is a number.
const TEXT_COLUMNS = new Set(['name', 'day']);
const plain = (rows: Row[]): Row[] =>
  rows.map((row) =>
    Object.fromEntries(
      Object.entries(row).map(([k, v]) => [k, TEXT_COLUMNS.has(k) || v === null ? v : Number(v)]),
    ),
  );

async function run(sql: string, params: unknown[] = []): Promise<Row[]> {
  const result = await db.query<Row>(sql, params);
  return plain(result.rows);
}

describe('SandPay report queries', { tags: ['@exercise'] }, () => {
  beforeAll(async () => {
    db = new PGlite();
    await db.exec(SCHEMA);
  });
  afterAll(async () => {
    await db.close();
  });

  it('revenueByMerchant lists every merchant, with 0 for a merchant without paid orders', async () => {
    expect(await run(revenueByMerchant)).toEqual([
      { name: 'Lumen Books', paid_orders: 4, paid_minor: 4849 },
      { name: 'Atlas Maps', paid_orders: 1, paid_minor: 4549 },
      { name: 'Kettle & Co', paid_orders: 1, paid_minor: 990 },
      { name: 'Quiet Cafe', paid_orders: 0, paid_minor: 0 },
    ]);
  });

  it('netPaidOrders subtracts all of an order’s refunds, counting each order once', async () => {
    expect(await run(netPaidOrders)).toEqual([
      { id: 101, amount_minor: 2599, refunded_minor: 1599, net_minor: 1000 },
      { id: 102, amount_minor: 1250, refunded_minor: 0, net_minor: 1250 },
      { id: 104, amount_minor: 700, refunded_minor: 0, net_minor: 700 },
      { id: 105, amount_minor: 990, refunded_minor: 990, net_minor: 0 },
      { id: 107, amount_minor: 4549, refunded_minor: 0, net_minor: 4549 },
      { id: 108, amount_minor: 300, refunded_minor: 0, net_minor: 300 },
    ]);
  });

  it('paidOrdersWithoutRefunds still finds them when a refund has no order (NULL)', async () => {
    expect(await run(paidOrdersWithoutRefunds)).toEqual([{ id: 102 }, { id: 104 }, { id: 107 }, { id: 108 }]);
  });

  it('dailyRevenue shows every day of the range in UTC, with 0 on days without sales', async () => {
    expect(await run(dailyRevenue, [1, '2026-11-09', '2026-11-13'])).toEqual([
      { day: '2026-11-09', paid_minor: 0 },
      { day: '2026-11-10', paid_minor: 3849 + 300 },
      { day: '2026-11-11', paid_minor: 0 },
      { day: '2026-11-12', paid_minor: 0 },
      { day: '2026-11-13', paid_minor: 700 },
    ]);
  });

  it('dailyRevenue only counts the merchant asked for', async () => {
    expect(await run(dailyRevenue, [2, '2026-11-11', '2026-11-12'])).toEqual([
      { day: '2026-11-11', paid_minor: 990 },
      { day: '2026-11-12', paid_minor: 0 },
    ]);
  });
});
