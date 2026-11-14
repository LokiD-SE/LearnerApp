// A data-access layer for SandPay orders.
//
// Contract:
// - Every value that comes from a caller travels as a $n parameter - never inside the SQL text.
// - Identifiers (column names, sort directions) can't be parameters, so `search` maps the caller's
//   `sortBy` through an allow-list to a fixed ORDER BY; anything else throws a RangeError.
// - `emailContains` matches literally: % and _ typed by a user are not LIKE wildcards.
// - `listByMerchant` returns newest first (created_at DESC, id DESC) using keyset pagination: pass the
//   previous page's `next` cursor as `after`; `next` is null on the last page. `limit` must be an
//   integer from 1 to 100 (RangeError otherwise).
// - Rows are mapped to camelCase `Order` objects. Drivers differ: node-postgres returns bigint columns
//   as strings, PGlite as numbers - accept both, and throw a RangeError for a value that isn't a safe
//   integer instead of silently losing precision.
export interface Queryable {
  query<T>(text: string, params?: unknown[]): Promise<{ rows: T[] }>;
}

export type OrderStatus = 'PENDING' | 'PAID' | 'REFUNDED';

export interface Order {
  id: number;
  merchantId: string;
  customerEmail: string;
  amountMinor: number;
  status: OrderStatus;
  createdAt: Date;
}

export interface NewOrder {
  merchantId: string;
  customerEmail: string;
  amountMinor: number;
}

export interface Cursor {
  createdAt: Date;
  id: number;
}

export interface Page {
  orders: Order[];
  next: Cursor | null;
}

export type SortBy = 'newest' | 'largest';

interface OrderRow {
  id: number | string;
  merchant_id: string;
  customer_email: string;
  amount_minor: number | string;
  status: OrderStatus;
  created_at: Date | string;
}

const COLUMNS = 'id, merchant_id, customer_email, amount_minor, status, created_at';

const ORDER_BY: Record<SortBy, string> = {
  newest: 'created_at DESC, id DESC',
  largest: 'amount_minor DESC, id DESC',
};

function toSafeInteger(value: number | string, column: string): number {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isSafeInteger(n)) throw new RangeError(`${column} ${String(value)} is not a safe integer`);
  return n;
}

function toOrder(row: OrderRow): Order {
  return {
    id: toSafeInteger(row.id, 'id'),
    merchantId: row.merchant_id,
    customerEmail: row.customer_email,
    amountMinor: toSafeInteger(row.amount_minor, 'amount_minor'),
    status: row.status,
    createdAt: row.created_at instanceof Date ? row.created_at : new Date(row.created_at),
  };
}

/** Escapes LIKE's wildcards (and the escape character itself) so the text matches literally. */
function likeLiteral(text: string): string {
  return text.replace(/[\\%_]/g, (c) => `\\${c}`);
}

export function createOrdersRepository(db: Queryable) {
  return {
    async findById(id: number): Promise<Order | null> {
      const { rows } = await db.query<OrderRow>(`SELECT ${COLUMNS} FROM orders WHERE id = $1`, [id]);
      return rows[0] ? toOrder(rows[0]) : null;
    },

    async create(input: NewOrder): Promise<Order> {
      const { rows } = await db.query<OrderRow>(
        `INSERT INTO orders (merchant_id, customer_email, amount_minor)
         VALUES ($1, $2, $3)
         RETURNING ${COLUMNS}`,
        [input.merchantId, input.customerEmail, input.amountMinor],
      );
      const row = rows[0];
      if (!row) throw new Error('INSERT ... RETURNING returned no row');
      return toOrder(row);
    },

    async listByMerchant(merchantId: string, options: { limit: number; after?: Cursor }): Promise<Page> {
      const { limit, after } = options;
      if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
        throw new RangeError(`limit must be an integer from 1 to 100, got ${limit}`);
      }
      // Fetch one extra row to know whether another page exists.
      const { rows } = after
        ? await db.query<OrderRow>(
            `SELECT ${COLUMNS} FROM orders
             WHERE merchant_id = $1 AND (created_at, id) < ($2, $3)
             ORDER BY created_at DESC, id DESC
             LIMIT $4`,
            [merchantId, after.createdAt, after.id, limit + 1],
          )
        : await db.query<OrderRow>(
            `SELECT ${COLUMNS} FROM orders
             WHERE merchant_id = $1
             ORDER BY created_at DESC, id DESC
             LIMIT $2`,
            [merchantId, limit + 1],
          );
      const orders = rows.slice(0, limit).map(toOrder);
      const last = orders.at(-1);
      const next = rows.length > limit && last ? { createdAt: last.createdAt, id: last.id } : null;
      return { orders, next };
    },

    async search(merchantId: string, options: { emailContains: string; sortBy: SortBy }): Promise<Order[]> {
      const orderBy = Object.hasOwn(ORDER_BY, options.sortBy) ? ORDER_BY[options.sortBy] : undefined;
      if (!orderBy) throw new RangeError(`unknown sortBy: ${String(options.sortBy)}`);
      const { rows } = await db.query<OrderRow>(
        `SELECT ${COLUMNS} FROM orders
         WHERE merchant_id = $1 AND customer_email LIKE '%' || $2 || '%'
         ORDER BY ${orderBy}`,
        [merchantId, likeLiteral(options.emailContains)],
      );
      return rows.map(toOrder);
    },
  };
}
