import { readFile } from 'node:fs/promises';
import type { PGlite } from '@electric-sql/pglite';
import { createSandPayDb } from '../../exercises/indexes/sandpay-db.js';

/** One node of EXPLAIN (FORMAT JSON) output. */
interface PlanNode {
  'Node Type': string;
  'Relation Name'?: string;
  'Index Name'?: string;
  Plans?: PlanNode[];
}

const QUERIES = {
  latestOrders: `SELECT id, status, amount_minor, created_at FROM orders
                 WHERE merchant_id = 42 ORDER BY created_at DESC, id DESC LIMIT 20`,
  byEmail: `SELECT id, status FROM orders WHERE lower(customer_email) = lower('customer777@example.test')`,
  oldestPending: `SELECT id, created_at FROM orders WHERE status = 'PENDING' ORDER BY created_at LIMIT 100`,
  paymentsOfPage: `SELECT * FROM payments WHERE order_id = ANY('{4242,4207,4401}'::int[])`,
};

let db: PGlite;

async function plan(sql: string): Promise<PlanNode[]> {
  const result = await db.query<{ 'QUERY PLAN': [{ Plan: PlanNode }] }>(`EXPLAIN (FORMAT JSON) ${sql}`);
  const root = result.rows[0]!['QUERY PLAN'][0].Plan;
  const all: PlanNode[] = [];
  const walk = (node: PlanNode) => {
    all.push(node);
    node.Plans?.forEach(walk);
  };
  walk(root);
  return all;
}

const seqScansOn = (nodes: PlanNode[], table: string) =>
  nodes.filter((n) => n['Node Type'] === 'Seq Scan' && n['Relation Name'] === table);
const sorts = (nodes: PlanNode[]) => nodes.filter((n) => n['Node Type'].endsWith('Sort'));
const describePlan = (nodes: PlanNode[]) =>
  nodes.map((n) => `${n['Node Type']}${n['Index Name'] ? ` using ${n['Index Name']}` : ''}`).join(' -> ');

describe('dashboard indexes (exercises/indexes/indexes.sql)', { tags: ['@exercise'] }, () => {
  beforeAll(async () => {
    db = await createSandPayDb(50_000);
    const sql = await readFile(new URL('../../exercises/indexes/indexes.sql', import.meta.url), 'utf8');
    await db.exec(sql);
    await db.exec('ANALYZE');
  }, 60_000);

  afterAll(async () => {
    await db.close();
  });

  it('creates at most 4 indexes besides the primary keys', async () => {
    const { rows } = await db.query<{ indexname: string }>(
      `SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname NOT LIKE '%_pkey'`,
    );
    expect(
      rows.length,
      `indexes found: ${rows.map((r) => r.indexname).join(', ') || 'none'}`,
    ).toBeGreaterThan(0);
    expect(rows.length).toBeLessThanOrEqual(4);
  });

  it('1. serves the latest orders of a merchant from an index, already sorted', async () => {
    const nodes = await plan(QUERIES.latestOrders);
    expect(seqScansOn(nodes, 'orders'), describePlan(nodes)).toEqual([]);
    expect(
      sorts(nodes),
      `a Sort step means the index doesn't deliver the order: ${describePlan(nodes)}`,
    ).toEqual([]);
    // The index must find merchant 42's entries directly - merchant_id as its first key column - rather
    // than walk every merchant's orders in date order and test merchant_id inside the index.
    const used = nodes.map((n) => n['Index Name']).filter((name): name is string => Boolean(name));
    expect(used.length, describePlan(nodes)).toBeGreaterThan(0);
    const { rows } = await db.query<{ name: string; first: string }>(
      `SELECT indexrelid::regclass::text AS name, pg_get_indexdef(indexrelid, 1, true) AS first
       FROM pg_index WHERE indexrelid::regclass::text = ANY($1)`,
      [used],
    );
    expect(
      rows.map((r) => r.first),
      `equality columns first - the leading column should be merchant_id: ${rows
        .map((r) => `${r.name} (${r.first}, ...)`)
        .join('; ')}`,
    ).toEqual(['merchant_id']);
  });

  it('2. finds orders by email without reading the whole table, whatever the case', async () => {
    const nodes = await plan(QUERIES.byEmail);
    expect(seqScansOn(nodes, 'orders'), describePlan(nodes)).toEqual([]);
  });

  it('3. takes the oldest pending orders from a partial index, already sorted', async () => {
    const nodes = await plan(QUERIES.oldestPending);
    expect(seqScansOn(nodes, 'orders'), describePlan(nodes)).toEqual([]);
    expect(sorts(nodes), describePlan(nodes)).toEqual([]);
    const used = nodes.map((n) => n['Index Name']).filter((name): name is string => Boolean(name));
    expect(used.length, describePlan(nodes)).toBeGreaterThan(0);
    const { rows } = await db.query<{ indexdef: string }>(
      `SELECT indexdef FROM pg_indexes WHERE indexname = ANY($1)`,
      [used],
    );
    expect(
      rows.some((r) => /\bWHERE\b/.test(r.indexdef)),
      `the index used should be partial (CREATE INDEX ... WHERE ...): ${rows.map((r) => r.indexdef).join('; ')}`,
    ).toBe(true);
  });

  it('3. keeps the pending-orders index small: under a tenth of the size of a full index', async () => {
    const { rows } = await db.query<{ indexdef: string; bytes: number }>(
      `SELECT indexdef, pg_relation_size(indexrelid)::int AS bytes
       FROM pg_index JOIN pg_indexes ON pg_indexes.indexname = pg_index.indexrelid::regclass::text
       WHERE pg_index.indrelid = 'orders'::regclass AND indexdef LIKE '%WHERE%'`,
    );
    expect(rows.length, 'no partial index on orders').toBeGreaterThan(0);
    const { rows: pk } = await db.query<{ bytes: number }>(
      `SELECT pg_relation_size('orders_pkey')::int AS bytes`,
    );
    for (const r of rows) expect(r.bytes, r.indexdef).toBeLessThan(pk[0]!.bytes / 10);
  });

  it('4. looks up the payments of a page of orders through an index', async () => {
    const nodes = await plan(QUERIES.paymentsOfPage);
    expect(seqScansOn(nodes, 'payments'), describePlan(nodes)).toEqual([]);
  });

  it('still answers every query correctly', async () => {
    const latest = await db.query<{ id: number }>(QUERIES.latestOrders);
    expect(latest.rows.map((r) => r.id).slice(0, 3)).toEqual([49841, 49641, 49441]);
    const byEmail = await db.query<{ id: number }>(QUERIES.byEmail);
    expect(byEmail.rows.map((r) => r.id).sort((a, b) => a - b)).toEqual([777, 20777, 40777]);
    const pending = await db.query<{ id: number }>(QUERIES.oldestPending);
    expect(pending.rows.slice(0, 2).map((r) => r.id)).toEqual([101, 202]);
    const payments = await db.query(QUERIES.paymentsOfPage);
    expect(payments.rows).toHaveLength(3); // 4242 is PENDING (no attempt), 4207 has two attempts
  });
});
