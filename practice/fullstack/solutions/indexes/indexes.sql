-- Reference solution: one index per query, each shaped by the query it serves.

-- 1. Equality column first, then the ORDER BY columns in the same order and direction: the index
--    returns one merchant's rows already sorted, so LIMIT 20 stops after 20 index entries (no Sort).
CREATE INDEX orders_merchant_created_id_idx ON orders (merchant_id, created_at DESC, id DESC);

-- 2. An expression index: the query filters on lower(customer_email), so that is what is indexed.
--    A plain index on customer_email can't serve lower(customer_email) = ...
CREATE INDEX orders_lower_email_idx ON orders (lower(customer_email));

-- 3. A partial index: only the ~1% PENDING rows are in it, sorted by created_at. The query's
--    WHERE status = 'PENDING' matches the index predicate, so the planner can use it.
CREATE INDEX orders_pending_created_idx ON orders (created_at) WHERE status = 'PENDING';

-- 4. A foreign key does not index the referencing column; looking payments up by order needs one.
CREATE INDEX payments_order_id_idx ON payments (order_id);
