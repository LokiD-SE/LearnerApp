-- SandPay merchant dashboard - the schema (PostgreSQL 18).
-- Reference solution. Amounts are integer minor units (2599 is 25.99) in bigint columns.

CREATE TABLE merchants (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name       text        NOT NULL CHECK (name <> ''),
  email      text        NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- One account per email address, whatever its capitalisation.
CREATE UNIQUE INDEX merchants_email_lower_key ON merchants (lower(email));

CREATE TABLE customers (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  merchant_id bigint NOT NULL REFERENCES merchants (id) ON DELETE RESTRICT,
  email       text   NOT NULL,
  -- the same person may buy from two merchants, but appears once per merchant
  UNIQUE (merchant_id, email)
);

CREATE TABLE orders (
  id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  merchant_id  bigint      NOT NULL REFERENCES merchants (id) ON DELETE RESTRICT,
  -- guest checkouts have no customer; deleting a customer keeps their orders
  customer_id  bigint      REFERENCES customers (id) ON DELETE SET NULL,
  amount_minor bigint      NOT NULL CHECK (amount_minor > 0),
  currency     char(3)     NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  status       text        NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PAID', 'FAILED')),
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE refunds (
  id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  -- a refund is part of its order: it goes when the order goes
  order_id     bigint      NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
  amount_minor bigint      NOT NULL CHECK (amount_minor > 0),
  reason       text,
  created_at   timestamptz NOT NULL DEFAULT now()
);
