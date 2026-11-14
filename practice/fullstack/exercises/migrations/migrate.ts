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
//
// The first draft below "works on my machine": it runs every migration in the order given, every time,
// outside any transaction, and remembers nothing. Rewrite migrate() to meet the contract.
// Useful PGlite calls: db.exec(sql) runs several statements; db.query(sql, params) runs one with $n
// parameters; db.transaction(async (tx) => { ... }) commits when the callback resolves and rolls back
// when it throws (use tx.exec / tx.query inside).
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

export async function migrate(db: PGlite, migrations: Migration[]): Promise<number[]> {
  const done: number[] = [];
  for (const m of migrations) {
    await db.exec(m.sql);
    done.push(m.version);
  }
  return done;
}
