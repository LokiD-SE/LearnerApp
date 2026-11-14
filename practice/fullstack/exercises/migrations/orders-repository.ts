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
//
// The first draft below builds SQL by gluing strings together. It passes a quick manual check with
// ordinary input. Rewrite it to meet the contract - keep the exported names and types.
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

function toOrder(row: OrderRow): Order {
  return {
    id: row.id as number,
    merchantId: row.merchant_id,
    customerEmail: row.customer_email,
    amountMinor: row.amount_minor as number,
    status: row.status,
    createdAt: row.created_at as Date,
  };
}

export function createOrdersRepository(db: Queryable) {
  return {
    async findById(id: number): Promise<Order | null> {
      const { rows } = await db.query<OrderRow>('SELECT * FROM orders WHERE id = ' + id);
      return rows[0] ? toOrder(rows[0]) : null;
    },

    async create(input: NewOrder): Promise<Order> {
      const { rows } = await db.query<OrderRow>(
        "INSERT INTO orders (merchant_id, customer_email, amount_minor) VALUES ('" +
          input.merchantId +
          "', '" +
          input.customerEmail +
          "', " +
          input.amountMinor +
          ') RETURNING *',
      );
      return toOrder(rows[0] as OrderRow);
    },

    async listByMerchant(merchantId: string, options: { limit: number; after?: Cursor }): Promise<Page> {
      const page = options.after ? 1 : 0; // TODO: real cursors
      const { rows } = await db.query<OrderRow>(
        "SELECT * FROM orders WHERE merchant_id = '" +
          merchantId +
          "' ORDER BY created_at DESC LIMIT " +
          options.limit +
          ' OFFSET ' +
          page * options.limit,
      );
      const orders = rows.map(toOrder);
      const last = orders.at(-1);
      return { orders, next: last ? { createdAt: last.createdAt, id: last.id } : null };
    },

    async search(merchantId: string, options: { emailContains: string; sortBy: SortBy }): Promise<Order[]> {
      const orderBy =
        options.sortBy === 'largest'
          ? 'amount_minor'
          : options.sortBy === 'newest'
            ? 'created_at'
            : options.sortBy;
      const { rows } = await db.query<OrderRow>(
        "SELECT * FROM orders WHERE merchant_id = '" +
          merchantId +
          "' AND customer_email LIKE '%" +
          options.emailContains +
          "%' ORDER BY " +
          orderBy +
          ' DESC',
      );
      return rows.map(toOrder);
    },
  };
}
