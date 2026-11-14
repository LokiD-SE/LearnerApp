// Exercise: health checks and graceful shutdown for the SandPay dashboard API (fictional).
// Tests: tests/deployment/lifecycle.test.ts
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

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export async function startServer(options: LifecycleOptions, port = 0): Promise<RunningServer> {
  let shuttingDown = false;
  const app = express();

  // Liveness: "is this process able to answer at all?" It must not depend on the database - a database
  // outage would otherwise make the platform restart every healthy copy of the app at once.
  app.get('/livez', (_req, res) => {
    res.json({ status: 'ok' });
  });

  // Readiness: "should traffic be sent here now?" False while shutting down or while a dependency is down.
  app.get('/readyz', async (_req, res) => {
    if (shuttingDown) {
      res.status(503).json({ status: 'shutting_down' });
      return;
    }
    try {
      await options.checkDatabase();
      res.json({ status: 'ready', checks: { database: 'ok' } });
    } catch {
      // The error may contain a host name or a connection string - log it, don't return it.
      options.log('readiness_check_failed', { check: 'database' });
      res.status(503).json({ status: 'unavailable', checks: { database: 'fail' } });
    }
  });

  app.use(options.routes);

  const server = createServer(app as RequestListener);
  await new Promise<void>((resolve) => server.listen(port, '127.0.0.1', resolve));
  const address = server.address();
  const actualPort = typeof address === 'object' && address !== null ? address.port : port;
  options.log('listening', { port: actualPort });

  let shutdownPromise: Promise<ShutdownResult> | undefined;

  async function runShutdown(reason: string): Promise<ShutdownResult> {
    shuttingDown = true;
    options.log('shutdown_started', { reason });

    // 1. Keep serving for a moment with readiness false, so the load balancer notices and stops routing here.
    await wait(options.drainDelayMs);

    // 2. Stop accepting connections and wait for in-flight requests, but not forever.
    const closed = new Promise<ShutdownResult>((resolve) => server.close(() => resolve('graceful')));
    let timer: NodeJS.Timeout | undefined;
    const timeout = new Promise<ShutdownResult>((resolve) => {
      timer = setTimeout(() => resolve('forced'), options.shutdownTimeoutMs);
    });
    const result = await Promise.race([closed, timeout]);
    clearTimeout(timer);
    if (result === 'forced') {
      options.log('shutdown_timeout', { timeoutMs: options.shutdownTimeoutMs });
      server.closeAllConnections();
    }

    // 3. Only now close the database: no request can still need it.
    await options.closeDatabase();
    options.log('shutdown_finished', { result });
    return result;
  }

  function shutdown(reason: string): Promise<ShutdownResult> {
    shutdownPromise ??= runShutdown(reason);
    return shutdownPromise;
  }

  return {
    server,
    port: actualPort,
    shutdown,
    installSignalHandlers(target, exit) {
      let exiting = false;
      for (const signal of ['SIGTERM', 'SIGINT'] as const) {
        target.on(signal, () => {
          // A second signal (an impatient Ctrl+C, a repeated SIGTERM) joins the shutdown already running.
          if (exiting) return;
          exiting = true;
          void shutdown(signal).then((result) => exit(result === 'graceful' ? 0 : 1));
        });
      }
    },
  };
}
