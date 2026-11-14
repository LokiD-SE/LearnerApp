// Reference solution: fix the N+1 query.
// Tests: tests/indexes/orders-with-payments.test.ts
//
// The SandPay dashboard shows a merchant's latest orders, each with its payment attempts.
// This version is correct but sends 1 query for the orders plus 1 query per order for its
// payments: 21 round trips for a page of 20, and 101 for a page of 100. Each round trip costs
// network latency on a real database server.
//
// Rewrite loadOrdersWithPayments so it sends AT MOST 2 queries, whatever `limit` is, and returns
// exactly the same result:
// - the merchant's `limit` newest orders: created_at newest first, ties by id descending;
// - each with `payments`: its attempts sorted by id ascending, or [] when it has none
//   (pending orders have no attempt yet);
// - [] for a merchant with no orders.
// Always pass values as query parameters ($1, $2...), never by building SQL strings.

/** Anything that can run a parameterised query - a PGlite instance, a pg Pool or Client. */
export interface Queryable {
  query<T>(sql: string, params?: unknown[]): Promise<{ rows: T[] }>;
}

export interface Payment {
  id: number;
  method: string;
  status: string;
  amountMinor: number;
}

export interface OrderWithPayments {
  id: number;
  status: string;
  amountMinor: number;
  createdAt: Date;
  payments: Payment[];
}

interface OrderRow {
  id: number;
  status: string;
  amount_minor: number;
  created_at: Date;
}

interface PaymentRow {
  id: number;
  order_id: number;
  method: string;
  status: string;
  amount_minor: number;
}

export async function loadOrdersWithPayments(
  db: Queryable,
  merchantId: number,
  limit = 20,
): Promise<OrderWithPayments[]> {
  // Query 1: the page of orders.
  const orders = await db.query<OrderRow>(
    `SELECT id, status, amount_minor, created_at FROM orders
     WHERE merchant_id = $1 ORDER BY created_at DESC, id DESC LIMIT $2`,
    [merchantId, limit],
  );
  if (orders.rows.length === 0) return [];

  // Query 2: every payment of every order on the page, in one round trip. The ids travel as one
  // array parameter - no SQL built from strings, and the same statement for any page size.
  const ids = orders.rows.map((o) => o.id);
  const payments = await db.query<PaymentRow>(
    `SELECT id, order_id, method, status, amount_minor FROM payments
     WHERE order_id = ANY($1::int[]) ORDER BY id`,
    [ids],
  );

  // Group in memory. A Map keeps it O(orders + payments) instead of filtering once per order.
  const byOrder = new Map<number, Payment[]>(ids.map((id) => [id, []]));
  for (const p of payments.rows) {
    byOrder.get(p.order_id)?.push({
      id: p.id,
      method: p.method,
      status: p.status,
      amountMinor: p.amount_minor,
    });
  }

  // The orders keep the order of query 1; payments are already sorted by id.
  return orders.rows.map((o) => ({
    id: o.id,
    status: o.status,
    amountMinor: o.amount_minor,
    createdAt: o.created_at,
    payments: byOrder.get(o.id) ?? [],
  }));
}
