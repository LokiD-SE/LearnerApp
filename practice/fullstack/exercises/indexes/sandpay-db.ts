// Shared by the indexes exercises - you don't need to change this file.
// A SandPay database in PGlite (PostgreSQL 18 compiled to WebAssembly): merchants, their orders and
// the payment attempts for each order. All data is fictional.
import { PGlite } from '@electric-sql/pglite';

export const SCHEMA = `
CREATE TABLE merchants (
  id   int PRIMARY KEY,
  name text NOT NULL
);
CREATE TABLE orders (
  id             int PRIMARY KEY,
  merchant_id    int NOT NULL REFERENCES merchants (id),
  customer_email text NOT NULL,
  status         text NOT NULL CHECK (status IN ('PENDING', 'PAID', 'FAILED')),
  amount_minor   int NOT NULL,
  created_at     timestamptz NOT NULL
);
CREATE TABLE payments (
  id           int PRIMARY KEY,
  order_id     int NOT NULL REFERENCES orders (id),
  method       text NOT NULL,
  status       text NOT NULL,
  amount_minor int NOT NULL,
  created_at   timestamptz NOT NULL
);`;

/**
 * Creates the schema and fills it: `orders` rows spread over 200 merchants (1% PENDING, 9% FAILED,
 * the rest PAID), customer emails in mixed case, one payment attempt per non-pending order and a
 * second attempt for every seventh order. Statistics are collected (ANALYZE) before it returns.
 */
export async function createSandPayDb(orders: number): Promise<PGlite> {
  const db = new PGlite();
  await db.exec(SCHEMA);
  await db.exec(`
    INSERT INTO merchants SELECT g, 'Merchant ' || g FROM generate_series(1, 200) g;
    INSERT INTO orders
    SELECT g,
           1 + (g % 200),
           'Customer' || (g % 20000) || '@Example.test',
           CASE WHEN g % 101 = 0 THEN 'PENDING' WHEN g % 10 = 0 THEN 'FAILED' ELSE 'PAID' END,
           100 + (g * 37) % 100000,
           timestamptz '2026-01-01 00:00:00+00' + make_interval(mins => g)
    FROM generate_series(1, ${orders}) g;
    INSERT INTO payments
    SELECT o.id, o.id, CASE WHEN o.id % 2 = 0 THEN 'card' ELSE 'upi' END,
           CASE WHEN o.status = 'FAILED' THEN 'DECLINED' ELSE 'CAPTURED' END,
           o.amount_minor, o.created_at + interval '5 seconds'
    FROM orders o WHERE o.status <> 'PENDING';
    INSERT INTO payments
    SELECT ${orders} + o.id, o.id, 'card', 'DECLINED', o.amount_minor, o.created_at + interval '2 seconds'
    FROM orders o WHERE o.status <> 'PENDING' AND o.id % 7 = 0;`);
  await db.exec('ANALYZE');
  return db;
}
