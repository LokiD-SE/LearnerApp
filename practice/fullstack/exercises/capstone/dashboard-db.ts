// Shared by the three capstone exercises and identical in solutions/ - you don't need to change this file.
// The SandPay merchant dashboard's database in PGlite (PostgreSQL 18 in WebAssembly). Everything is
// fictional: the merchants, payment ids and amounts. Amounts are integer minor units (5000 is 50.00).
import { PGlite } from '@electric-sql/pglite';

export const SCHEMA = `
  CREATE TABLE merchants (
    id   integer PRIMARY KEY,
    name text    NOT NULL
  );
  CREATE TABLE payments (
    id             text        PRIMARY KEY,
    merchant_id    integer     NOT NULL REFERENCES merchants (id),
    amount_minor   bigint      NOT NULL CHECK (amount_minor > 0),
    currency       char(3)     NOT NULL,
    refunded_minor bigint      NOT NULL DEFAULT 0,
    created_at     timestamptz NOT NULL,
    -- The database's last line of defence: a payment is never refunded below 0 or above its amount.
    CHECK (refunded_minor >= 0 AND refunded_minor <= amount_minor)
  );
  CREATE TABLE refunds (
    id           integer     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payment_id   text        NOT NULL REFERENCES payments (id),
    amount_minor bigint      NOT NULL CHECK (amount_minor > 0),
    created_at   timestamptz NOT NULL DEFAULT now()
  );
  -- One row per idempotency key, scoped to the merchant: two merchants may pick the same key.
  -- status_code and response stay NULL until the request's outcome is stored.
  CREATE TABLE idempotency_keys (
    merchant_id integer     NOT NULL REFERENCES merchants (id),
    key         text        NOT NULL,
    fingerprint text        NOT NULL,
    status_code integer,
    response    jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (merchant_id, key)
  );
  CREATE INDEX payments_merchant_created ON payments (merchant_id, created_at DESC);
`;

export const SEED = `
  INSERT INTO merchants VALUES (1, 'Asha Books'), (2, 'Ravi Electronics');
  INSERT INTO payments (id, merchant_id, amount_minor, currency, refunded_minor, created_at) VALUES
    ('pay_1001', 1, 5000, 'EUR', 0,    '2026-11-10T09:15:00Z'),
    ('pay_1002', 1, 1250, 'EUR', 0,    '2026-11-12T14:02:00Z'),
    ('pay_1003', 1, 2599, 'EUR', 2599, '2026-11-01T08:30:00Z'),
    ('pay_2001', 2, 89900, 'EUR', 0,   '2026-11-11T11:45:00Z');
`;

export async function createDashboardDb(): Promise<PGlite> {
  const db = new PGlite();
  await db.exec(SCHEMA);
  await db.exec(SEED);
  return db;
}

/** Resets the data between tests without paying PGlite's start-up time again. */
export async function resetDashboardDb(db: PGlite): Promise<void> {
  await db.exec('TRUNCATE idempotency_keys, refunds, payments, merchants RESTART IDENTITY CASCADE');
  await db.exec(SEED);
}
