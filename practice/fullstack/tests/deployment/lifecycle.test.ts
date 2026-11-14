import { EventEmitter } from 'node:events';
import { request as httpRequest } from 'node:http';
import express from 'express';
import {
  startServer,
  type LifecycleOptions,
  type RunningServer,
} from '../../exercises/deployment/lifecycle.js';

/** A request whose response the test releases by hand - an in-flight request during shutdown. */
function slowRoute() {
  let release: () => void = () => undefined;
  const started = new Promise<void>((resolveStarted) => {
    routes.get('/reports/slow', async (_req, res) => {
      resolveStarted();
      await new Promise<void>((resolve) => (release = resolve));
      res.json({ report: 'done' });
    });
  });
  return { started, release: () => release() };
}

let routes: express.Express;
let events: string[];
let running: RunningServer | undefined;

function options(overrides: Partial<LifecycleOptions> = {}): LifecycleOptions {
  return {
    routes,
    checkDatabase: async () => undefined,
    closeDatabase: async () => {
      events.push('database_closed');
    },
    drainDelayMs: 150,
    shutdownTimeoutMs: 2_000,
    log: (event) => events.push(event),
    ...overrides,
  };
}

/** GET over a fresh connection (no keep-alive pool), so a closed server shows up as a connection error. */
function get(port: number, path: string): Promise<{ status: number; body: unknown }> {
  return new Promise((resolve, reject) => {
    const req = httpRequest({ host: '127.0.0.1', port, path, agent: false }, (res) => {
      let text = '';
      res.setEncoding('utf8');
      res.on('data', (chunk: string) => (text += chunk));
      res.on('end', () =>
        resolve({ status: res.statusCode ?? 0, body: text ? JSON.parse(text) : undefined }),
      );
      res.on('error', reject);
    });
    req.on('error', reject);
    req.end();
  });
}

beforeEach(() => {
  routes = express();
  routes.get('/merchants/mch_1001', (_req, res) => {
    res.json({ id: 'mch_1001' });
  });
  events = [];
});

afterEach(async () => {
  if (running?.server.listening) {
    running.server.closeAllConnections();
    await new Promise((resolve) => running?.server.close(resolve));
  }
  running = undefined;
});

describe('health checks', { tags: ['@exercise'] }, () => {
  test('/livez and /readyz answer 200 while everything is up, and the routes still work', async () => {
    running = await startServer(options());
    expect(await get(running.port, '/livez')).toEqual({ status: 200, body: { status: 'ok' } });
    expect(await get(running.port, '/readyz')).toEqual({
      status: 200,
      body: { status: 'ready', checks: { database: 'ok' } },
    });
    expect(await get(running.port, '/merchants/mch_1001')).toEqual({ status: 200, body: { id: 'mch_1001' } });
  });

  test('a database outage makes /readyz 503 without leaking the error - /livez stays 200', async () => {
    running = await startServer(
      options({
        checkDatabase: async () => {
          throw new Error('connect ECONNREFUSED db.internal:5432');
        },
      }),
    );
    const ready = await get(running.port, '/readyz');
    expect(ready).toEqual({ status: 503, body: { status: 'unavailable', checks: { database: 'fail' } } });
    expect(JSON.stringify(ready.body)).not.toContain('db.internal');
    expect(await get(running.port, '/livez')).toEqual({ status: 200, body: { status: 'ok' } });
  });

  test('liveness does not call the database at all', async () => {
    let checks = 0;
    running = await startServer(
      options({
        checkDatabase: async () => {
          checks += 1;
        },
      }),
    );
    await get(running.port, '/livez');
    await get(running.port, '/livez');
    expect(checks).toBe(0);
  });
});

describe('graceful shutdown', { tags: ['@exercise'] }, () => {
  test('readiness turns 503 at once, but requests are still served during the drain delay', async () => {
    running = await startServer(options({ drainDelayMs: 400 }));
    const done = running.shutdown('test');
    expect(await get(running.port, '/readyz')).toEqual({ status: 503, body: { status: 'shutting_down' } });
    expect(await get(running.port, '/merchants/mch_1001')).toEqual({ status: 200, body: { id: 'mch_1001' } });
    expect(await done).toBe('graceful');
  });

  test('an in-flight request finishes before the database is closed', async () => {
    const slow = slowRoute();
    running = await startServer(options());
    const inFlight = get(running.port, '/reports/slow');
    await slow.started;

    const done = running.shutdown('SIGTERM');
    await new Promise((resolve) => setTimeout(resolve, 300)); // past the drain delay
    expect(events).not.toContain('database_closed');
    events.push('response_released');
    slow.release();

    expect(await inFlight).toEqual({ status: 200, body: { report: 'done' } });
    expect(await done).toBe('graceful');
    expect(events.indexOf('database_closed')).toBeGreaterThan(events.indexOf('response_released'));
    expect(events.filter((event) => event === 'database_closed')).toHaveLength(1);
  });

  test('stops accepting new connections after the drain delay', async () => {
    const slow = slowRoute();
    running = await startServer(options());
    const inFlight = get(running.port, '/reports/slow');
    await slow.started;
    const done = running.shutdown('SIGTERM');
    await new Promise((resolve) => setTimeout(resolve, 300));
    await expect(get(running.port, '/livez')).rejects.toThrow(/ECONNREFUSED|ECONNRESET/);
    slow.release();
    await inFlight;
    await done;
  });

  test('a request that never ends is cut off after shutdownTimeoutMs, and the database is still closed', async () => {
    slowRoute(); // never released
    running = await startServer(options({ drainDelayMs: 50, shutdownTimeoutMs: 300 }));
    const inFlight = get(running.port, '/reports/slow').catch((error: Error) => error);
    await new Promise((resolve) => setTimeout(resolve, 50));
    const started = Date.now();
    expect(await running.shutdown('SIGTERM')).toBe('forced');
    expect(Date.now() - started).toBeLessThan(1_500);
    expect(await inFlight).toBeInstanceOf(Error);
    expect(events).toContain('database_closed');
  });

  test('calling shutdown twice runs it once', async () => {
    running = await startServer(options({ drainDelayMs: 50 }));
    const first = running.shutdown('SIGTERM');
    const second = running.shutdown('SIGINT');
    expect(await Promise.all([first, second])).toEqual(['graceful', 'graceful']);
    expect(events.filter((event) => event === 'database_closed')).toHaveLength(1);
  });
});

describe('signal handlers', { tags: ['@exercise'] }, () => {
  test('SIGTERM shuts down gracefully and then exits with 0 - once, even if the signal repeats', async () => {
    running = await startServer(options({ drainDelayMs: 50 }));
    const fakeProcess = new EventEmitter();
    const exits: number[] = [];
    const exited = new Promise<void>((resolve) => {
      running?.installSignalHandlers(fakeProcess, (code) => {
        exits.push(code);
        resolve();
      });
    });

    fakeProcess.emit('SIGTERM');
    expect(exits).toEqual([]); // not before the shutdown has finished
    fakeProcess.emit('SIGTERM');
    await exited;
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(exits).toEqual([0]);
    expect(events).toContain('database_closed');
  });

  test('SIGINT is handled too, and a forced shutdown exits with 1', async () => {
    slowRoute();
    running = await startServer(options({ drainDelayMs: 50, shutdownTimeoutMs: 200 }));
    void get(running.port, '/reports/slow').catch(() => undefined);
    await new Promise((resolve) => setTimeout(resolve, 50));
    const fakeProcess = new EventEmitter();
    const code = await new Promise<number>((resolve) => {
      running?.installSignalHandlers(fakeProcess, resolve);
      fakeProcess.emit('SIGINT');
      setTimeout(() => resolve(-1), 2_000); // -1: exit was never called
    });
    expect(code).toBe(1);
  });
});
