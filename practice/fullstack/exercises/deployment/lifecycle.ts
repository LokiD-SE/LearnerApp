// Exercise: health checks and graceful shutdown for the SandPay dashboard API (fictional).
// Tests: tests/deployment/lifecycle.test.ts
//
// This first draft drops requests on every deploy and gets the app restarted whenever the database
// blips. Fix it:
//   1. /livez answers 200 { status: 'ok' } and must NOT call the database.
//   2. /readyz answers 200 { status: 'ready', checks: { database: 'ok' } } when checkDatabase()
//      resolves, and 503 { status: 'unavailable', checks: { database: 'fail' } } when it rejects -
//      without the error text in the body. Once a shutdown has started it answers
//      503 { status: 'shutting_down' }.
//   3. shutdown(reason): readiness false at once; keep serving for drainDelayMs; then server.close()
//      and wait for in-flight requests; if that takes longer than shutdownTimeoutMs, cut the
//      connections (server.closeAllConnections()) and report 'forced'. Close the database LAST,
//      exactly once. A second call returns the same promise.
//   4. installSignalHandlers(target, exit): on SIGTERM or SIGINT run the shutdown, then exit(0)
//      after a graceful one or exit(1) after a forced one - exit once, however many signals arrive.
import type { EventEmitter } from 'node:events';
import { createServer, type RequestListener, type Server } from 'node:http';
import express, { type Express } from 'express';

export interface LifecycleOptions {
  /** The business routes. Mounted after /livez and /readyz. */
  routes: Express;
  /** Resolves if the database answers (for example `SELECT 1`); rejects if it doesn't. */
  checkDatabase(): Promise<void>;
  /** Closes the connection pool. Call it exactly once, after the last request has finished. */
  closeDatabase(): Promise<void>;
  /** How long to keep serving after readiness turns false, so load balancers stop sending traffic. */
  drainDelayMs: number;
  /** The longest a shutdown may take before open connections are cut. */
  shutdownTimeoutMs: number;
  /** One structured log line per lifecycle event. */
  log(event: string, fields?: Record<string, unknown>): void;
}

export type ShutdownResult = 'graceful' | 'forced';

export interface RunningServer {
  server: Server;
  port: number;
  /** Starts a shutdown; calling it again returns the same promise. */
  shutdown(reason: string): Promise<ShutdownResult>;
  /** Shuts down on SIGTERM and SIGINT, then calls exit(0) after a graceful shutdown or exit(1) after a forced one. */
  installSignalHandlers(target: Pick<EventEmitter, 'on'>, exit: (code: number) => void): void;
}

export async function startServer(options: LifecycleOptions, port = 0): Promise<RunningServer> {
  const app = express();

  // One health endpoint for everything, as the first draft had it.
  const health: express.RequestHandler = async (_req, res) => {
    try {
      await options.checkDatabase();
      res.json({ status: 'ok' });
    } catch (error) {
      res.status(500).json({ status: 'error', error: String(error) });
    }
  };
  app.get('/livez', health);
  app.get('/readyz', health);

  app.use(options.routes);

  const server = createServer(app as RequestListener);
  await new Promise<void>((resolve) => server.listen(port, '127.0.0.1', resolve));
  const address = server.address();
  const actualPort = typeof address === 'object' && address !== null ? address.port : port;
  options.log('listening', { port: actualPort });

  async function shutdown(reason: string): Promise<ShutdownResult> {
    options.log('shutdown_started', { reason });
    await options.closeDatabase();
    server.closeAllConnections();
    server.close();
    return 'graceful';
  }

  return {
    server,
    port: actualPort,
    shutdown,
    installSignalHandlers(target, exit) {
      target.on('SIGTERM', () => {
        void shutdown('SIGTERM');
        exit(0);
      });
    },
  };
}
