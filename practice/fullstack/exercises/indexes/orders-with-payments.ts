// Exercise: fix the N+1 query.
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
  const orders = await db.query<OrderRow>(
    `SELECT id, status, amount_minor, created_at FROM orders
     WHERE merchant_id = $1 ORDER BY created_at DESC, id DESC LIMIT $2`,
    [merchantId, limit],
  );
  const result: OrderWithPayments[] = [];
  for (const order of orders.rows) {
    // One more round trip for every order: the N in "N+1".
    const payments = await db.query<PaymentRow>(
      `SELECT id, order_id, method, status, amount_minor FROM payments WHERE order_id = $1 ORDER BY id`,
      [order.id],
    );
    result.push({
      id: order.id,
      status: order.status,
      amountMinor: order.amount_minor,
      createdAt: order.created_at,
      payments: payments.rows.map((p) => ({
        id: p.id,
        method: p.method,
        status: p.status,
        amountMinor: p.amount_minor,
      })),
    });
  }
  return result;
}
