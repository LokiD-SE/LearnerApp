// SandPay merchant dashboard - report queries (PostgreSQL 18).
// Exercise: replace each placeholder with a query that returns exactly what its comment asks for.
// The schema and the data are in tests/sql/reports.test.ts. Amounts are integer minor units.
// Run: npx vitest run tests/sql/reports.test.ts

/**
 * Every merchant - including merchants with no paid orders - with the number of PAID orders and their
 * total. Columns: name, paid_orders, paid_minor (0, never NULL). Largest paid_minor first, then by name.
 */
export const revenueByMerchant = `SELECT 'TODO' AS todo`;

/**
 * PAID orders net of their refunds. Columns: id, amount_minor, refunded_minor (0 when none),
 * net_minor. Ordered by id.
 */
export const netPaidOrders = `SELECT 'TODO' AS todo`;

/**
 * Ids of PAID orders that have no refund at all, ordered by id. Column: id.
 * (refunds.order_id may be NULL for refunds not yet matched to an order - see the test data.)
 */
export const paidOrdersWithoutRefunds = `SELECT 'TODO' AS todo`;

/**
 * One merchant's PAID revenue for every UTC day from $2 to $3 inclusive - days without sales included,
 * with 0. Parameters: $1 merchant id, $2 first day, $3 last day (dates as 'YYYY-MM-DD').
 * Columns: day (text 'YYYY-MM-DD'), paid_minor. Ordered by day.
 */
export const dailyRevenue = `SELECT 'TODO' AS todo WHERE $1::bigint IS NOT NULL AND $2::date <= $3::date`;
