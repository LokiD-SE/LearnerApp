import type { PGlite } from '@electric-sql/pglite';

/**
 * SandPay's refund tables (fictional). Amounts are integers in minor units.
 *
 * - `payments.refunded_minor` is the running total of refunds; the CHECK constraint is the
 *   database's last line of defence for the invariant 0 <= refunded <= captured.
 * - `refunds` holds one row per refund.
 * - `outbox` holds events to publish after the transaction commits (the outbox pattern): a
 *   separate worker reads it and calls other systems, so no network call happens inside the
 *   transaction.
 */
export const SCHEMA = `
  CREATE TABLE payments (
    id             text    PRIMARY KEY,
    currency       text    NOT NULL,
    captured_minor bigint  NOT NULL CHECK (captured_minor >= 0),
    refunded_minor bigint  NOT NULL DEFAULT 0,
    CHECK (refunded_minor >= 0 AND refunded_minor <= captured_minor)
  );
  CREATE TABLE refunds (
    id           serial PRIMARY KEY,
    payment_id   text   NOT NULL REFERENCES payments (id),
    amount_minor bigint NOT NULL CHECK (amount_minor > 0),
    reason       text   NOT NULL
  );
  CREATE TABLE outbox (
    id         serial PRIMARY KEY,
    event_type text   NOT NULL,
    payload    jsonb  NOT NULL
  );
`;

export async function createSchema(db: PGlite): Promise<void> {
  await db.exec(SCHEMA);
}
