// Shared by the exercise and the solution (identical files): a small SandPay database in PGlite with two
// merchants, so a test can check that merchant 1 never sees or changes merchant 2's data.
// Everything here is fictional: example.test e-mail addresses, made-up amounts in minor units.
import { PGlite } from '@electric-sql/pglite';

export interface Order {
  id: number;
  merchantId: number;
  customerEmail: string;
  amountMinor: number;
  currency: string;
  status: 'PAID' | 'REFUNDED';
}

export async function createSandpayDb(): Promise<PGlite> {
  const db = new PGlite();
  await db.exec(`
    CREATE TABLE merchants (
      id   integer PRIMARY KEY,
      name text NOT NULL
    );
    CREATE TABLE orders (
      id             integer PRIMARY KEY,
      merchant_id    integer NOT NULL REFERENCES merchants (id),
      customer_email text    NOT NULL,
      amount_minor   bigint  NOT NULL CHECK (amount_minor > 0),
      currency       char(3) NOT NULL,
      status         text    NOT NULL DEFAULT 'PAID'
    );
    CREATE TABLE refunds (
      id           integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      order_id     integer NOT NULL REFERENCES orders (id),
      amount_minor bigint  NOT NULL CHECK (amount_minor > 0),
      created_at   timestamptz NOT NULL DEFAULT now()
    );
    INSERT INTO merchants VALUES (1, 'Asha Books'), (2, 'Ravi Electronics');
    INSERT INTO orders (id, merchant_id, customer_email, amount_minor, currency) VALUES
      (101, 1, 'meera@example.test', 2599, 'EUR'),
      (102, 1, 'asha.reader@example.test', 1200, 'EUR'),
      (201, 2, 'karan@example.test', 89900, 'EUR'),
      (202, 2, 'asha.k@example.test', 45000, 'EUR');
  `);
  return db;
}

/** Selects an order with camelCase names, for the queries in the app. */
export const ORDER_COLUMNS = `id, merchant_id AS "merchantId", customer_email AS "customerEmail",
  amount_minor::integer AS "amountMinor", currency, status`;
