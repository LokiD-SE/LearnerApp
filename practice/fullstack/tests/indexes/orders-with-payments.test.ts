import type { PGlite } from '@electric-sql/pglite';
import {
  loadOrdersWithPayments,
  type OrderWithPayments,
  type Queryable,
} from '../../exercises/indexes/orders-with-payments.js';
import { createSandPayDb } from '../../exercises/indexes/sandpay-db.js';

let db: PGlite;

/** Wraps the database and records every SQL statement sent through it. */
function counting(): Queryable & { statements: string[] } {
  const statements: string[] = [];
  return {
    statements,
    query: <T>(sql: string, params?: unknown[]) => {
      statements.push(sql);
      return db.query<T>(sql, params);
    },
  };
}

/** The expected result, built independently with one aggregate query. */
async function expected(merchantId: number, limit: number): Promise<OrderWithPayments[]> {
  const { rows } = await db.query<{ result: OrderWithPayments[] | null }>(
    `SELECT json_agg(o ORDER BY o."createdAt" DESC, o.id DESC) AS result FROM (
       SELECT id, status, amount_minor AS "amountMinor", created_at AS "createdAt",
              COALESCE((SELECT json_agg(json_build_object('id', p.id, 'method', p.method,
                          'status', p.status, 'amountMinor', p.amount_minor) ORDER BY p.id)
                        FROM payments p WHERE p.order_id = orders.id), '[]') AS payments
       FROM orders WHERE merchant_id = $1 ORDER BY created_at DESC, id DESC LIMIT $2) o`,
    [merchantId, limit],
  );
  return (rows[0]!.result ?? []).map((o) => ({ ...o, createdAt: new Date(o.createdAt) }));
}

describe(
  'loadOrdersWithPayments (exercises/indexes/orders-with-payments.ts)',
  { tags: ['@exercise'] },
  () => {
    beforeAll(async () => {
      db = await createSandPayDb(20_000);
      await db.exec(`INSERT INTO merchants VALUES (999, 'Merchant without orders')`);
      await db.exec(`CREATE INDEX payments_order_id_idx ON payments (order_id)`);
    }, 60_000);

    afterAll(async () => {
      await db.close();
    });

    it('returns the newest orders first, each with its payment attempts', async () => {
      const page = await loadOrdersWithPayments(counting(), 42);
      expect(page).toHaveLength(20);
      expect(page.slice(0, 3).map((o) => o.id)).toEqual([19841, 19641, 19441]);
      expect(page).toEqual(await expected(42, 20));
    });

    it('sorts an order with two attempts by payment id, and gives a pending order no attempts', async () => {
      const page = await loadOrdersWithPayments(counting(), 42, 100);
      const twoAttempts = page.find((o) => o.payments.length === 2);
      expect(twoAttempts, 'an order with a retry').toBeDefined();
      expect(twoAttempts!.payments.map((p) => p.status)).toEqual(['CAPTURED', 'DECLINED']);
      expect(twoAttempts!.payments[0]!.id).toBeLessThan(twoAttempts!.payments[1]!.id);
      const pending = page.find((o) => o.status === 'PENDING');
      expect(pending, 'a pending order').toBeDefined();
      expect(pending!.payments).toEqual([]);
      expect(page).toEqual(await expected(42, 100));
    });

    it('sends at most 2 queries for a page of 20', async () => {
      const spy = counting();
      await loadOrdersWithPayments(spy, 42, 20);
      expect(spy.statements.length, `queries sent:\n${spy.statements.join('\n---\n')}`).toBeLessThanOrEqual(
        2,
      );
    });

    it('still sends at most 2 queries for a page of 100', async () => {
      const spy = counting();
      const page = await loadOrdersWithPayments(spy, 7, 100);
      expect(page).toHaveLength(100);
      expect(spy.statements.length).toBeLessThanOrEqual(2);
      expect(page).toEqual(await expected(7, 100));
    });

    it('returns [] for a merchant without orders', async () => {
      const spy = counting();
      expect(await loadOrdersWithPayments(spy, 999)).toEqual([]);
      expect(spy.statements.length).toBeLessThanOrEqual(2);
    });

    it('passes ids as parameters instead of writing them into the SQL', async () => {
      const spy = counting();
      const page = await loadOrdersWithPayments(spy, 42, 20);
      const ids = page.map((o) => String(o.id));
      for (const sql of spy.statements) for (const id of ids) expect(sql).not.toContain(id);
    });
  },
);
