// The orders table the repository exercise works on (shared by the exercise and the solution).
import type { PGlite } from '@electric-sql/pglite';

export const ORDERS_SCHEMA = `
CREATE TABLE orders (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  merchant_id text NOT NULL,
  customer_email text NOT NULL,
  amount_minor bigint NOT NULL CHECK (amount_minor > 0),
  status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PAID', 'REFUNDED')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX orders_merchant_created_idx ON orders (merchant_id, created_at DESC, id DESC);
`;

export async function createOrdersTable(db: PGlite): Promise<void> {
  await db.exec(ORDERS_SCHEMA);
}
