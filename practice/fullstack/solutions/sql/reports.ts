// SandPay merchant dashboard - report queries (PostgreSQL 18). Reference solution.
// Each query runs against the schema in tests/sql/reports.test.ts. Amounts are integer minor units.

/**
 * Every merchant - including merchants with no paid orders - with the number of PAID orders and their
 * total. Columns: name, paid_orders, paid_minor (0, never NULL). Largest paid_minor first, then by name.
 */
export const revenueByMerchant = `
  SELECT m.name,
         count(o.id)                     AS paid_orders,
         coalesce(sum(o.amount_minor), 0) AS paid_minor
  FROM merchants m
  LEFT JOIN orders o
         ON o.merchant_id = m.id
        AND o.status = 'PAID'          -- in ON, not WHERE, so merchants without paid orders stay
  GROUP BY m.id, m.name
  ORDER BY paid_minor DESC, m.name
`;

/**
 * PAID orders net of their refunds. Columns: id, amount_minor, refunded_minor (0 when none),
 * net_minor. Ordered by id.
 */
export const netPaidOrders = `
  WITH refunded AS (
    SELECT order_id, sum(amount_minor) AS refunded_minor
    FROM refunds
    GROUP BY order_id
  )
  SELECT o.id,
         o.amount_minor,
         coalesce(r.refunded_minor, 0)                  AS refunded_minor,
         o.amount_minor - coalesce(r.refunded_minor, 0) AS net_minor
  FROM orders o
  LEFT JOIN refunded r ON r.order_id = o.id
  WHERE o.status = 'PAID'
  ORDER BY o.id
`;

/**
 * Ids of PAID orders that have no refund at all, ordered by id. Column: id.
 * (refunds.order_id may be NULL for refunds not yet matched to an order - see the test data.)
 */
export const paidOrdersWithoutRefunds = `
  SELECT o.id
  FROM orders o
  WHERE o.status = 'PAID'
    AND NOT EXISTS (SELECT 1 FROM refunds r WHERE r.order_id = o.id)
  ORDER BY o.id
`;

/**
 * One merchant's PAID revenue for every UTC day from $2 to $3 inclusive - days without sales included,
 * with 0. Parameters: $1 merchant id, $2 first day, $3 last day (dates as 'YYYY-MM-DD').
 * Columns: day (text 'YYYY-MM-DD'), paid_minor. Ordered by day.
 */
export const dailyRevenue = `
  SELECT d.day::date::text                AS day,
         coalesce(sum(o.amount_minor), 0) AS paid_minor
  FROM generate_series($2::date, $3::date, interval '1 day') AS d(day)
  LEFT JOIN orders o
         ON o.merchant_id = $1
        AND o.status = 'PAID'
        AND (o.created_at AT TIME ZONE 'UTC')::date = d.day::date
  GROUP BY d.day
  ORDER BY d.day
`;
