// Runs exercises/sql/schema.sql in PGlite (PostgreSQL 18 compiled to WebAssembly) and checks that good
// rows go in and bad rows are rejected with the right kind of error.
import { readFileSync } from 'node:fs';
import { PGlite } from '@electric-sql/pglite';

const schema = readFileSync(new URL('../../exercises/sql/schema.sql', import.meta.url), 'utf8');

// SQLSTATE codes from the PostgreSQL manual, appendix A.
const NOT_NULL = '23502';
const FOREIGN_KEY = '23503';
const UNIQUE = '23505';
const CHECK = '23514';
const TOO_LONG = '22001'; // a char(3) column rejects 'EURO' before any CHECK runs
const RESTRICT = '23001'; // ON DELETE RESTRICT; the default NO ACTION reports FOREIGN_KEY

let db: PGlite;

async function rejects(sql: string, ...codes: string[]): Promise<void> {
  let error: unknown;
  try {
    await db.query(sql);
  } catch (e) {
    error = e;
  }
  expect(error, `expected SQLSTATE ${codes.join(' or ')} for: ${sql}`).toBeDefined();
  expect(codes, `wrong error for: ${sql}`).toContain((error as { code?: string }).code);
}

async function seed(): Promise<void> {
  await db.exec(`
    INSERT INTO merchants (name, email) VALUES ('Lumen Books', 'ops@lumen.example'), ('Kettle & Co', 'pay@kettle.example');
    INSERT INTO customers (merchant_id, email) VALUES (1, 'asha@example.com'), (2, 'asha@example.com');
    INSERT INTO orders (merchant_id, customer_id, amount_minor, currency, status)
      VALUES (1, 1, 2599, 'EUR', 'PAID'), (2, 2, 990, 'EUR', 'PAID'), (1, NULL, 1250, 'EUR', 'PENDING');
    INSERT INTO refunds (order_id, amount_minor, reason) VALUES (1, 599, 'damaged cover');
  `);
}

async function columnType(table: string, column: string): Promise<string | undefined> {
  const result = await db.query<{ data_type: string }>(
    'SELECT data_type FROM information_schema.columns WHERE table_name = $1 AND column_name = $2',
    [table, column],
  );
  return result.rows[0]?.data_type;
}

describe('the SandPay schema', { tags: ['@exercise'] }, () => {
  beforeEach(async () => {
    db = new PGlite();
    await db.exec(schema);
  });
  afterEach(async () => {
    await db.close();
  });

  it('accepts a valid merchant, customers, orders (one a guest checkout) and a refund', async () => {
    await seed();
    const counts = await db.query<{ n: number }>(
      `SELECT (SELECT count(*) FROM merchants) + (SELECT count(*) FROM customers)
            + (SELECT count(*) FROM orders) + (SELECT count(*) FROM refunds) AS n`,
    );
    expect(Number(counts.rows[0]?.n)).toBe(8);
  });

  it('stores amounts as exact integers (bigint) and times as timestamptz', async () => {
    expect(await columnType('orders', 'amount_minor')).toBe('bigint');
    expect(await columnType('refunds', 'amount_minor')).toBe('bigint');
    for (const table of ['merchants', 'orders', 'refunds']) {
      expect(await columnType(table, 'created_at'), `${table}.created_at`).toBe('timestamp with time zone');
    }
  });

  it('fills created_at and an order status of PENDING when they are not given', async () => {
    await db.exec(`INSERT INTO merchants (name, email) VALUES ('Lumen Books', 'ops@lumen.example')`);
    await db.exec(`INSERT INTO orders (merchant_id, amount_minor, currency) VALUES (1, 500, 'EUR')`);
    const order = await db.query<{ status: string; has_time: boolean }>(
      'SELECT status, created_at IS NOT NULL AS has_time FROM orders',
    );
    expect(order.rows[0]).toEqual({ status: 'PENDING', has_time: true });
    const merchant = await db.query<{ has_time: boolean }>(
      'SELECT created_at IS NOT NULL AS has_time FROM merchants',
    );
    expect(merchant.rows[0]?.has_time).toBe(true);
  });

  it('requires a merchant name and email, and an order amount, currency and merchant', async () => {
    await seed();
    await rejects(`INSERT INTO merchants (name) VALUES ('No Email Ltd')`, NOT_NULL);
    await rejects(`INSERT INTO merchants (email) VALUES ('noname@example.com')`, NOT_NULL);
    await rejects(`INSERT INTO orders (merchant_id, currency) VALUES (1, 'EUR')`, NOT_NULL);
    await rejects(`INSERT INTO orders (merchant_id, amount_minor) VALUES (1, 500)`, NOT_NULL);
    await rejects(`INSERT INTO orders (amount_minor, currency) VALUES (500, 'EUR')`, NOT_NULL);
  });

  it('allows one merchant per email address, ignoring capitalisation', async () => {
    await seed();
    await rejects(`INSERT INTO merchants (name, email) VALUES ('Lumen Again', 'ops@lumen.example')`, UNIQUE);
    await rejects(
      `INSERT INTO merchants (name, email) VALUES ('Lumen Shouting', 'OPS@Lumen.example')`,
      UNIQUE,
    );
  });

  it('allows an email once per merchant, but the same email at two merchants', async () => {
    await seed();
    await rejects(`INSERT INTO customers (merchant_id, email) VALUES (1, 'asha@example.com')`, UNIQUE);
    await expect(
      db.query(`INSERT INTO customers (merchant_id, email) VALUES (1, 'ben@example.com')`),
    ).resolves.toBeDefined();
  });

  it('rejects zero and negative amounts on orders and refunds', async () => {
    await seed();
    await rejects(`INSERT INTO orders (merchant_id, amount_minor, currency) VALUES (1, 0, 'EUR')`, CHECK);
    await rejects(`INSERT INTO orders (merchant_id, amount_minor, currency) VALUES (1, -500, 'EUR')`, CHECK);
    await rejects(`INSERT INTO refunds (order_id, amount_minor) VALUES (1, 0)`, CHECK);
  });

  it('accepts only three capital letters as a currency and only PENDING, PAID or FAILED as a status', async () => {
    await seed();
    for (const currency of ['eur', 'EURO', 'E1R', 'EU']) {
      await rejects(
        `INSERT INTO orders (merchant_id, amount_minor, currency) VALUES (1, 500, '${currency}')`,
        CHECK,
        TOO_LONG,
      );
    }
    await rejects(
      `INSERT INTO orders (merchant_id, amount_minor, currency, status) VALUES (1, 500, 'EUR', 'paid')`,
      CHECK,
    );
  });

  it('rejects rows that point at a merchant, customer or order that does not exist', async () => {
    await seed();
    await rejects(`INSERT INTO customers (merchant_id, email) VALUES (99, 'x@example.com')`, FOREIGN_KEY);
    await rejects(
      `INSERT INTO orders (merchant_id, amount_minor, currency) VALUES (99, 500, 'EUR')`,
      FOREIGN_KEY,
    );
    await rejects(
      `INSERT INTO orders (merchant_id, customer_id, amount_minor, currency) VALUES (1, 99, 500, 'EUR')`,
      FOREIGN_KEY,
    );
    await rejects(`INSERT INTO refunds (order_id, amount_minor) VALUES (99, 100)`, FOREIGN_KEY);
  });

  it('refuses to delete a merchant that still has customers or orders', async () => {
    await seed();
    await rejects('DELETE FROM merchants WHERE id = 1', RESTRICT, FOREIGN_KEY);
  });

  it('keeps the orders of a deleted customer, without a customer', async () => {
    await seed();
    await db.exec('DELETE FROM customers WHERE id = 1');
    const orders = await db.query<{ id: number; customer_id: number | null }>(
      'SELECT id, customer_id FROM orders WHERE merchant_id = 1 ORDER BY id',
    );
    expect(orders.rows.map((r) => [Number(r.id), r.customer_id])).toEqual([
      [1, null],
      [3, null],
    ]);
  });

  it('deletes the refunds of a deleted order with it', async () => {
    await seed();
    await db.exec('DELETE FROM orders WHERE id = 1');
    const refunds = await db.query<{ n: number }>('SELECT count(*) AS n FROM refunds');
    expect(Number(refunds.rows[0]?.n)).toBe(0);
  });
});
