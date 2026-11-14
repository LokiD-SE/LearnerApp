// The code under test for the "fake, spy and fake timers" exercise. It is correct - don't change it.
// (The same file is in solutions/testing.)
import { PGlite } from '@electric-sql/pglite';

export type OrderStatus = 'PENDING' | 'PAID' | 'FAILED';

export interface PendingOrder {
  id: string;
  customerEmail: string;
  /** Milliseconds since the epoch, like Date.now(). */
  createdAt: number;
  status: OrderStatus;
  reminded: boolean;
}

/** Where the reminder service finds orders. The real one is PostgreSQL; tests can use a fake. */
export interface PendingOrders {
  add(order: PendingOrder): Promise<void>;
  setStatus(id: string, status: OrderStatus): Promise<void>;
  /** PENDING, not yet reminded, created at or before `cutoff` - oldest first, ties by id. Copies. */
  dueForReminder(cutoff: number): Promise<PendingOrder[]>;
  markReminded(id: string): Promise<void>;
}

export interface ReminderMessage {
  to: string;
  template: 'payment-reminder';
  orderId: string;
}

export interface Mailer {
  send(message: ReminderMessage): Promise<void>;
}

/** An order still PENDING 30 minutes after it was created gets one reminder e-mail. */
export const REMIND_AFTER_MS = 30 * 60_000;
/** The service looks for due orders once a minute. */
export const CHECK_EVERY_MS = 60_000;

export interface ReminderService {
  start(): void;
  stop(): void;
}

export type CreateReminderService = (deps: { orders: PendingOrders; mailer: Mailer }) => ReminderService;

/**
 * Every CHECK_EVERY_MS after start(), sends one reminder to each due order's customer and marks the
 * order reminded. If sending fails, the order is not marked, so the next check tries again. stop()
 * ends the checks.
 */
export const createReminderService: CreateReminderService = ({ orders, mailer }) => {
  let timer: ReturnType<typeof setInterval> | undefined;
  let checking = false;

  async function check(): Promise<void> {
    if (checking) return; // a slow check is still running - skip this tick
    checking = true;
    try {
      const due = await orders.dueForReminder(Date.now() - REMIND_AFTER_MS);
      for (const order of due) {
        try {
          await mailer.send({ to: order.customerEmail, template: 'payment-reminder', orderId: order.id });
          await orders.markReminded(order.id);
        } catch {
          // not marked: the next check tries this order again
        }
      }
    } finally {
      checking = false;
    }
  }

  return {
    start() {
      timer ??= setInterval(() => void check(), CHECK_EVERY_MS);
    },
    stop() {
      clearInterval(timer);
      timer = undefined;
    },
  };
};

/** The production repository: PostgreSQL (here PGlite, a real PostgreSQL engine in WebAssembly). */
export class PgPendingOrders implements PendingOrders {
  private constructor(private readonly db: PGlite) {}

  static async create(): Promise<PgPendingOrders> {
    const db = new PGlite();
    await db.exec(`
      CREATE TABLE orders (
        id text PRIMARY KEY,
        customer_email text NOT NULL,
        created_at bigint NOT NULL,
        status text NOT NULL CHECK (status IN ('PENDING', 'PAID', 'FAILED')),
        reminded boolean NOT NULL DEFAULT false
      )`);
    return new PgPendingOrders(db);
  }

  async add(o: PendingOrder): Promise<void> {
    await this.db.query(
      'INSERT INTO orders (id, customer_email, created_at, status, reminded) VALUES ($1, $2, $3, $4, $5)',
      [o.id, o.customerEmail, o.createdAt, o.status, o.reminded],
    );
  }

  async setStatus(id: string, status: OrderStatus): Promise<void> {
    await this.db.query('UPDATE orders SET status = $2 WHERE id = $1', [id, status]);
  }

  async dueForReminder(cutoff: number): Promise<PendingOrder[]> {
    const result = await this.db.query<{
      id: string;
      customer_email: string;
      created_at: string | number;
      status: OrderStatus;
      reminded: boolean;
    }>(
      `SELECT id, customer_email, created_at, status, reminded FROM orders
       WHERE status = 'PENDING' AND NOT reminded AND created_at <= $1
       ORDER BY created_at, id`,
      [cutoff],
    );
    return result.rows.map((r) => ({
      id: r.id,
      customerEmail: r.customer_email,
      createdAt: Number(r.created_at),
      status: r.status,
      reminded: r.reminded,
    }));
  }

  async markReminded(id: string): Promise<void> {
    await this.db.query('UPDATE orders SET reminded = true WHERE id = $1', [id]);
  }

  async close(): Promise<void> {
    await this.db.close();
  }
}
