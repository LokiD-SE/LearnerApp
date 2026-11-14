import { PGlite } from '@electric-sql/pglite';
import {
  createOrdersRepository,
  type Queryable,
  type SortBy,
} from '../../exercises/migrations/orders-repository.js';
import { createOrdersTable } from '../../exercises/migrations/orders-schema.js';

interface Call {
  text: string;
  params: unknown[];
}

/** Wraps PGlite and records every statement the repository sends. */
function recording(db: PGlite): Queryable & { calls: Call[] } {
  const calls: Call[] = [];
  return {
    calls,
    async query<T>(text: string, params: unknown[] = []) {
      calls.push({ text, params });
      return db.query<T>(text, params);
    },
  };
}

async function setup() {
  const db = new PGlite();
  await createOrdersTable(db);
  await db.query(
    `INSERT INTO orders (merchant_id, customer_email, amount_minor, status, created_at) VALUES
       ('m_42', 'asha@example.test',    2599, 'PAID',     '2026-11-01T09:00:00Z'),
       ('m_42', 'li@example.test',      1000, 'PENDING',  '2026-11-02T09:00:00Z'),
       ('m_42', 'ravi_k@example.test',  7500, 'PAID',     '2026-11-03T09:00:00Z'),
       ('m_42', 'raviak@example.test',   500, 'REFUNDED', '2026-11-03T09:00:00Z'),
       ('m_42', 'sam@example.test',     4200, 'PAID',     '2026-11-04T09:00:00Z'),
       ('m_7',  'other@example.test',  50000, 'PAID',     '2026-11-05T09:00:00Z')`,
  );
  const db2 = recording(db);
  return { db, rec: db2, repo: createOrdersRepository(db2) };
}

async function count(db: PGlite) {
  const { rows } = await db.query<{ n: number }>('SELECT count(*)::int AS n FROM orders');
  return rows[0]?.n;
}

async function outcome(promise: Promise<unknown>): Promise<unknown> {
  try {
    return await promise;
  } catch (error) {
    return error;
  }
}

describe('OrdersRepository - parameterised data access', { tags: ['@exercise'] }, () => {
  test('create stores the order and returns it mapped to camelCase', async () => {
    const { repo } = await setup();
    const order = await repo.create({
      merchantId: 'm_42',
      customerEmail: 'new@example.test',
      amountMinor: 1999,
    });
    expect(order).toEqual({
      id: 7,
      merchantId: 'm_42',
      customerEmail: 'new@example.test',
      amountMinor: 1999,
      status: 'PENDING',
      createdAt: expect.any(Date),
    });
    expect(await repo.findById(7)).toEqual(order);
    expect(await repo.findById(999)).toBeNull();
  });

  test("an apostrophe in an email is data, not SQL (o'brien)", async () => {
    const { repo } = await setup();
    const order = await outcome(
      repo.create({ merchantId: 'm_42', customerEmail: "o'brien@example.test", amountMinor: 300 }),
    );
    expect(order).toMatchObject({ customerEmail: "o'brien@example.test" });
  });

  test('caller values travel only as $n parameters, never in the SQL text', async () => {
    const { rec, repo } = await setup();
    await repo.create({ merchantId: 'm_42', customerEmail: 'zoe@example.test', amountMinor: 1234 });
    await repo.findById(3);
    await repo.listByMerchant('m_42', { limit: 2 });
    await repo.search('m_42', { emailContains: 'ravi', sortBy: 'largest' });
    for (const value of ['m_42', 'zoe@example.test', '1234', 'ravi']) {
      for (const call of rec.calls)
        expect(call.text, `"${value}" found in: ${call.text}`).not.toContain(value);
    }
    expect(rec.calls.every((c) => c.params.length > 0)).toBe(true);
  });

  test("an injection in the search text can't reach other merchants' orders", async () => {
    const { repo } = await setup();
    // glued into SQL this becomes: ... LIKE '%' OR merchant_id <> '%' ... - every row of every merchant
    const result = await outcome(
      repo.search('m_42', { emailContains: "' OR merchant_id <> '", sortBy: 'newest' }),
    );
    expect(result).toEqual([]);
  });

  test('an injected merchant id cannot widen the list to other merchants', async () => {
    const { repo } = await setup();
    const page = await outcome(repo.listByMerchant("m_42' OR '1'='1", { limit: 10 }));
    expect(page).toEqual({ orders: [], next: null });
  });

  test('a stacked DELETE in the search text is just text', async () => {
    const { db, repo } = await setup();
    const result = await outcome(
      repo.search('m_42', { emailContains: "'; DELETE FROM orders; --", sortBy: 'newest' }),
    );
    expect(result).toEqual([]);
    expect(await count(db)).toBe(6);
  });

  test('% and _ in the search text match literally, not as wildcards', async () => {
    const { repo } = await setup();
    expect(await outcome(repo.search('m_42', { emailContains: '%', sortBy: 'newest' }))).toEqual([]);
    const underscore = await outcome(repo.search('m_42', { emailContains: 'ravi_', sortBy: 'newest' }));
    // only ravi_k@... - not raviak@..., which "_" as a wildcard would also match
    expect((underscore as { customerEmail: string }[]).map((o) => o.customerEmail)).toEqual([
      'ravi_k@example.test',
    ]);
  });

  test('sortBy comes from an allow-list; anything else is rejected and nothing runs', async () => {
    const { db, repo } = await setup();
    const largest = await repo.search('m_42', { emailContains: 'example', sortBy: 'largest' });
    expect(largest.map((o) => o.amountMinor)).toEqual([7500, 4200, 2599, 1000, 500]);
    const evil = 'amount_minor; DROP TABLE orders; --' as SortBy;
    const error = await outcome(repo.search('m_42', { emailContains: 'example', sortBy: evil }));
    expect(error).toBeInstanceOf(RangeError);
    const proto = await outcome(
      repo.search('m_42', { emailContains: 'example', sortBy: 'toString' as SortBy }),
    );
    expect(proto).toBeInstanceOf(RangeError);
    expect(await count(db)).toBe(6);
  });

  test('keyset pagination walks every order once, newest first, with a tie-breaker', async () => {
    const { repo } = await setup();
    const seen: number[] = [];
    let page = await repo.listByMerchant('m_42', { limit: 2 });
    seen.push(...page.orders.map((o) => o.id));
    // at most 10 pages, so a cursor that never ends fails the test instead of hanging it
    for (let pages = 1; page.next && pages < 10; pages++) {
      page = await repo.listByMerchant('m_42', { limit: 2, after: page.next });
      seen.push(...page.orders.map((o) => o.id));
    }
    // orders 3 and 4 share created_at: id DESC breaks the tie
    expect(seen).toEqual([5, 4, 3, 2, 1]);
    expect(page.next).toBeNull();
  });

  test('the last full page says there is no next page', async () => {
    const { repo } = await setup();
    const first = await repo.listByMerchant('m_42', { limit: 3 });
    expect(first.next).not.toBeNull();
    const second = await repo.listByMerchant('m_42', { limit: 2, after: first.next ?? undefined });
    expect(second.orders.map((o) => o.id)).toEqual([2, 1]);
    expect(second.next).toBeNull();
  });

  test('limit must be an integer from 1 to 100', async () => {
    const { repo } = await setup();
    for (const limit of [0, 101, 2.5]) {
      expect(await outcome(repo.listByMerchant('m_42', { limit }))).toBeInstanceOf(RangeError);
    }
  });

  test('maps node-postgres style rows: bigint strings become numbers, unsafe ones throw', async () => {
    const createdAt = new Date('2026-11-14T06:55:40.543Z');
    const pgStyle: Queryable = {
      async query<T>() {
        const row = {
          id: '12',
          merchant_id: 'm_42',
          customer_email: 'asha@example.test',
          amount_minor: '2599',
          status: 'PAID',
          created_at: createdAt,
        };
        return { rows: [row] as T[] };
      },
    };
    expect(await createOrdersRepository(pgStyle).findById(12)).toEqual({
      id: 12,
      merchantId: 'm_42',
      customerEmail: 'asha@example.test',
      amountMinor: 2599,
      status: 'PAID',
      createdAt,
    });
    const huge: Queryable = {
      async query<T>() {
        const row = {
          id: '9007199254740993',
          merchant_id: 'm_42',
          customer_email: 'a@example.test',
          amount_minor: '1',
          status: 'PAID',
          created_at: createdAt,
        };
        return { rows: [row] as T[] };
      },
    };
    expect(await outcome(createOrdersRepository(huge).findById(1))).toBeInstanceOf(RangeError);
  });
});
