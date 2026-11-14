-- SandPay merchant dashboard - the schema (PostgreSQL 18).
-- Exercise: the tables and columns are here, but nothing stops bad data. Add the keys, defaults and
-- constraints that tests/sql/schema.test.ts asks for. Amounts are integer minor units (2599 is 25.99).
-- Run: npx vitest run tests/sql/schema.test.ts

CREATE TABLE merchants (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name       text,
  email      text,
  created_at timestamp
);
-- TODO: one merchant per email address, whatever its capitalisation.

CREATE TABLE customers (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  merchant_id bigint,
  email       text
  -- TODO: the same email may appear once per merchant.
);

CREATE TABLE orders (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  merchant_id  bigint,
  customer_id  bigint,
  amount_minor double precision,
  currency     text,
  status       text,
  created_at   timestamp
);

CREATE TABLE refunds (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  order_id     bigint,
  amount_minor double precision,
  reason       text,
  created_at   timestamp
);
