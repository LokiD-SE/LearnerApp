// Exercise: make the SandPay merchant API (fictional) a good citizen in a container - liveness and
// readiness endpoints for health checks, and a graceful shutdown when `docker stop` (or Compose, or an
// orchestrator) sends SIGTERM.
// Tests: tests/docker/graceful-shutdown.test.ts

import type { EventEmitter } from 'node:events';
import type { Server } from 'node:http';
import express, { type Express } from 'express';

export interface HealthDeps {
  /** True once shutdown has started. */
  isShuttingDown(): boolean;
  /** Resolves when the database answers (for example `SELECT 1`); rejects or hangs when it doesn't. */
  pingDatabase(): Promise<void>;
  /** How long /readyz waits for pingDatabase before calling it a failure. Default 1000 ms. */
  pingTimeoutMs?: number;
}

/**
 * Builds the health routes WITHOUT calling listen().
 *
 * - `GET /healthz` (liveness: "is this process able to serve at all?") -> always 200
 *   `{ "status": "ok" }`. It must NOT call the database: a database outage is not a reason to restart
 *   the API, and a liveness check that depends on it turns one outage into a restart loop.
 * - `GET /readyz` (readiness: "send me traffic?") -> 200 `{ "status": "ready" }` when not shutting
 *   down and the database ping resolves within `pingTimeoutMs`; otherwise 503 with
 *   `{ "status": "shutting_down" }` (checked first, without pinging) or `{ "status": "db_unavailable" }`.
 * - Both responses carry `Cache-Control: no-store`.
 */
export function createHealthApp(deps: HealthDeps): Express {
  const app = express();
  // TODO: /healthz must not touch the database; /readyz must answer 503 while shutting down or when
  // the ping fails or takes longer than pingTimeoutMs; both must send Cache-Control: no-store.
  app.get('/healthz', async (req, res) => {
    await deps.pingDatabase();
    res.json({ status: 'ok' });
  });
  app.get('/readyz', (req, res) => {
    res.json({ status: 'ready' });
  });
  return app;
}

export interface ShutdownDeps {
  /** The listening HTTP server. */
  server: Server;
  /** Closes what the app holds open - the database pool, queues. Called once, after the server closed. */
  closeResources(): Promise<void>;
  /** Exits the process. In production `process.exit`; tests pass a spy. */
  exit(code: number): void;
  /**
   * The longest the shutdown may take before giving up: keep it BELOW the container's stop grace
   * period (10 s by default for docker stop and Compose), so the app exits on its own terms instead
   * of being killed with SIGKILL.
   */
  graceMs: number;
  log?(message: string): void;
}

/**
 * Listens for SIGTERM and SIGINT on `signals` (in production `process`) and shuts down gracefully:
 *
 * 1. on the FIRST signal, mark the app as shutting down (so /readyz answers 503) and log
 *    "<SIGNAL> received, shutting down";
 * 2. stop accepting connections with `server.close()` and let requests in flight finish. close() only
 *    closes the keep-alive connections that are idle AT THAT MOMENT: a connection whose request
 *    finishes later stays open until the client or the keep-alive timeout drops it (seconds). So
 *    while shutting down, call `server.closeIdleConnections()` every 100 ms until the server closed;
 * 3. when the server has closed, await `closeResources()`, then `exit(0)` - or `exit(1)` if
 *    closeResources rejects;
 * 4. if all of that takes longer than `graceMs`, force it: `server.closeAllConnections()` and `exit(1)`;
 * 5. a second signal while shutting down changes nothing (no second close, no second exit).
 *
 * `exit` is called exactly once. Returns `isShuttingDown`, for createHealthApp.
 */
export function installGracefulShutdown(
  signals: EventEmitter,
  deps: ShutdownDeps,
): { isShuttingDown(): boolean } {
  // TODO: replace this version. It exits at once, dropping every request in flight, never closes
  // the server or the resources, and never reports that it is shutting down.
  signals.on('SIGTERM', () => deps.exit(0));
  return { isShuttingDown: () => false };
}
