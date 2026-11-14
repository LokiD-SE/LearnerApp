import { PGlite } from '@electric-sql/pglite';
import { checksum, migrate, MigrationError, type Migration } from '../../exercises/migrations/migrate.js';

const createOrders: Migration = {
  version: 1,
  name: 'create_orders',
  sql: `CREATE TABLE orders (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id text NOT NULL,
    amount_minor bigint NOT NULL CHECK (amount_minor > 0)
  );`,
};
const addStatus: Migration = {
  version: 2,
  name: 'add_order_status',
  sql: `ALTER TABLE orders ADD COLUMN status text NOT NULL DEFAULT 'PENDING';
        CREATE INDEX orders_pending_idx ON orders (merchant_id) WHERE status = 'PENDING';`,
};
const createRefunds: Migration = {
  version: 3,
  name: 'create_refunds',
  sql: `CREATE TABLE refunds (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES orders (id),
    amount_minor bigint NOT NULL CHECK (amount_minor > 0)
  );`,
};
// Creates a table, then fails on its second statement (the column does not exist).
const broken: Migration = {
  version: 4,
  name: 'broken_backfill',
  sql: `CREATE TABLE payouts (id bigint PRIMARY KEY);
        UPDATE orders SET no_such_column = 1;`,
};

async function history(db: PGlite) {
  const { rows } = await db.query<{ version: number; name: string; checksum: string }>(
    'SELECT version, name, checksum FROM schema_migrations ORDER BY version',
  );
  return rows;
}

async function tableExists(db: PGlite, name: string) {
  const { rows } = await db.query<{ t: string | null }>('SELECT to_regclass($1)::text AS t', [name]);
  return rows[0]?.t !== null;
}

async function rejection(promise: Promise<unknown>): Promise<unknown> {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  throw new Error('expected migrate() to throw a MigrationError, but it resolved');
}

describe('migrate - a schema migration runner', { tags: ['@exercise'] }, () => {
  test('applies pending migrations in version order and records each one', async () => {
    const db = new PGlite();
    const applied = await migrate(db, [addStatus, createOrders]);
    expect(applied).toEqual([1, 2]);
    expect(await history(db)).toEqual([
      { version: 1, name: 'create_orders', checksum: checksum(createOrders.sql) },
      { version: 2, name: 'add_order_status', checksum: checksum(addStatus.sql) },
    ]);
    await db.query("INSERT INTO orders (merchant_id, amount_minor) VALUES ('m_42', 2599)");
    const { rows } = await db.query<{ status: string }>('SELECT status FROM orders');
    expect(rows).toEqual([{ status: 'PENDING' }]);
  });

  test('running it again applies nothing and changes nothing', async () => {
    const db = new PGlite();
    await migrate(db, [createOrders, addStatus]);
    expect(await migrate(db, [createOrders, addStatus])).toEqual([]);
    expect(await history(db)).toHaveLength(2);
  });

  test('applies only the new migration after a deploy adds one', async () => {
    const db = new PGlite();
    await migrate(db, [createOrders, addStatus]);
    expect(await migrate(db, [createOrders, addStatus, createRefunds])).toEqual([3]);
    expect(await tableExists(db, 'refunds')).toBe(true);
  });

  test('a failing migration is rolled back completely and stops the run', async () => {
    const db = new PGlite();
    await migrate(db, [createOrders, addStatus]);
    const after: Migration = { version: 5, name: 'never_runs', sql: 'CREATE TABLE never_runs (id int);' };
    const error = await rejection(migrate(db, [createOrders, addStatus, broken, after]));
    expect(error).toBeInstanceOf(MigrationError);
    expect(String((error as Error).message)).toContain('4');
    expect((error as Error).cause).toBeDefined();
    // the first statement of the failed migration was undone with it
    expect(await tableExists(db, 'payouts')).toBe(false);
    expect(await tableExists(db, 'never_runs')).toBe(false);
    expect((await history(db)).map((r) => r.version)).toEqual([1, 2]);
  });

  test('earlier migrations of the same run stay applied when a later one fails', async () => {
    const db = new PGlite();
    await rejection(migrate(db, [createOrders, addStatus, createRefunds, broken]));
    expect((await history(db)).map((r) => r.version)).toEqual([1, 2, 3]);
    expect(await tableExists(db, 'refunds')).toBe(true);
  });

  test('refuses a migration that was edited after it was applied', async () => {
    const db = new PGlite();
    await migrate(db, [createOrders, addStatus]);
    const edited = { ...addStatus, sql: addStatus.sql.replace("'PENDING'", "'NEW'") };
    const error = await rejection(migrate(db, [createOrders, edited, createRefunds]));
    expect(error).toBeInstanceOf(MigrationError);
    expect(String((error as Error).message)).toContain('2');
    expect(await tableExists(db, 'refunds')).toBe(false);
  });

  test('refuses to run when an applied migration is missing from the code', async () => {
    const db = new PGlite();
    await migrate(db, [createOrders, addStatus]);
    const error = await rejection(migrate(db, [createOrders]));
    expect(error).toBeInstanceOf(MigrationError);
  });

  test('refuses a pending migration older than the newest applied one', async () => {
    const db = new PGlite();
    await migrate(db, [createOrders, createRefunds]);
    const error = await rejection(migrate(db, [createOrders, addStatus, createRefunds]));
    expect(error).toBeInstanceOf(MigrationError);
    expect(String((error as Error).message)).toContain('2');
    const { rows } = await db.query<{ n: number }>(
      "SELECT count(*)::int AS n FROM information_schema.columns WHERE table_name = 'orders' AND column_name = 'status'",
    );
    expect(rows[0]?.n).toBe(0);
  });

  test('rejects duplicate or invalid versions before touching the database', async () => {
    const db = new PGlite();
    const twin = { ...createRefunds, version: 1 };
    expect(await rejection(migrate(db, [createOrders, twin]))).toBeInstanceOf(MigrationError);
    expect(await tableExists(db, 'orders')).toBe(false);
    const zero = { ...createOrders, version: 0 };
    expect(await rejection(migrate(db, [zero]))).toBeInstanceOf(MigrationError);
    expect(await tableExists(db, 'orders')).toBe(false);
  });
});
