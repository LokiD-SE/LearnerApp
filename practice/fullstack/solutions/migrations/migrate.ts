// A small schema-migration runner for PostgreSQL (PGlite here; the same SQL works on a server).
//
// Contract:
// - `migrations` is the full list the code knows, in any order. Each has a positive integer `version`
//   (unique), a `name` and the `sql` to run (one or more statements).
// - The runner keeps a `schema_migrations` table: version (primary key), name, checksum (SHA-256 hex
//   of the sql) and applied_at. It creates the table if it is missing.
// - Before running anything it checks the history and throws a MigrationError if:
//     * two migrations share a version, or a version is not a positive integer;
//     * an applied migration is missing from the list (code older than the database);
//     * an applied migration's sql has changed since it ran (checksum differs) - fix forward instead;
//     * a pending migration has a lower version than the newest applied one (it would run out of order).
// - Pending migrations run in ascending version order, each in its OWN transaction together with its
//   schema_migrations row, so a failing migration leaves no trace and earlier ones stay applied. The
//   failure is rethrown as a MigrationError naming the version, with the database error as `cause`;
//   later migrations do not run.
// - Returns the versions applied by this call, in order. Running it again applies nothing.
import { createHash } from 'node:crypto';
import type { PGlite } from '@electric-sql/pglite';

export interface Migration {
  version: number;
  name: string;
  sql: string;
}

export class MigrationError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = 'MigrationError';
  }
}

export function checksum(sql: string): string {
  return createHash('sha256').update(sql, 'utf8').digest('hex');
}

interface AppliedRow {
  version: number;
  checksum: string;
}

export async function migrate(db: PGlite, migrations: Migration[]): Promise<number[]> {
  const sorted = [...migrations].sort((a, b) => a.version - b.version);
  const seen = new Set<number>();
  for (const m of sorted) {
    if (!Number.isSafeInteger(m.version) || m.version <= 0) {
      throw new MigrationError(`migration "${m.name}" has an invalid version: ${m.version}`);
    }
    if (seen.has(m.version)) throw new MigrationError(`two migrations have version ${m.version}`);
    seen.add(m.version);
  }

  await db.exec(`CREATE TABLE IF NOT EXISTS schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
  )`);

  const { rows } = await db.query<AppliedRow>(
    'SELECT version, checksum FROM schema_migrations ORDER BY version',
  );
  const applied = new Map(rows.map((r) => [r.version, r.checksum]));
  const byVersion = new Map(sorted.map((m) => [m.version, m]));

  for (const [version, sum] of applied) {
    const known = byVersion.get(version);
    if (!known) throw new MigrationError(`migration ${version} is applied but missing from the code`);
    if (checksum(known.sql) !== sum) {
      throw new MigrationError(
        `migration ${version} (${known.name}) was edited after it was applied - add a new migration instead`,
      );
    }
  }

  const newest = rows.length > 0 ? Math.max(...applied.keys()) : 0;
  const pending = sorted.filter((m) => !applied.has(m.version));
  const early = pending.find((m) => m.version < newest);
  if (early) {
    throw new MigrationError(
      `migration ${early.version} (${early.name}) is older than the newest applied migration ${newest} - it would run out of order`,
    );
  }

  const done: number[] = [];
  for (const m of pending) {
    try {
      await db.transaction(async (tx) => {
        await tx.exec(m.sql);
        await tx.query('INSERT INTO schema_migrations (version, name, checksum) VALUES ($1, $2, $3)', [
          m.version,
          m.name,
          checksum(m.sql),
        ]);
      });
    } catch (error) {
      throw new MigrationError(`migration ${m.version} (${m.name}) failed and was rolled back`, {
        cause: error,
      });
    }
    done.push(m.version);
  }
  return done;
}
