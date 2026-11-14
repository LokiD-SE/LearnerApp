import { EventEmitter } from 'node:events';
import { createServer, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import request from 'supertest';
import {
  createHealthApp,
  installGracefulShutdown,
  type ShutdownDeps,
} from '../../exercises/docker/graceful-shutdown.js';

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe('createHealthApp', { tags: ['@exercise'] }, () => {
  test('/healthz answers 200 without touching the database, even when it is down', async () => {
    const pingDatabase = vi.fn(() => Promise.reject(new Error('ECONNREFUSED db:5432')));
    const app = createHealthApp({ isShuttingDown: () => false, pingDatabase });
    const res = await request(app).get('/healthz');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: 'ok' });
    expect(res.headers['cache-control']).toBe('no-store');
    expect(pingDatabase).not.toHaveBeenCalled();
  });

  test('/readyz answers 200 when the database answers', async () => {
    const app = createHealthApp({ isShuttingDown: () => false, pingDatabase: () => Promise.resolve() });
    const res = await request(app).get('/readyz');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: 'ready' });
    expect(res.headers['cache-control']).toBe('no-store');
  });

  test('/readyz answers 503 db_unavailable when the ping fails', async () => {
    const app = createHealthApp({
      isShuttingDown: () => false,
      pingDatabase: () => Promise.reject(new Error('ECONNREFUSED db:5432')),
    });
    const res = await request(app).get('/readyz');
    expect(res.status).toBe(503);
    expect(res.body).toEqual({ status: 'db_unavailable' });
    expect(res.headers['cache-control']).toBe('no-store');
  });

  test('/readyz gives up on a ping that hangs after pingTimeoutMs', async () => {
    const app = createHealthApp({
      isShuttingDown: () => false,
      pingDatabase: () => new Promise<void>(() => {}),
      pingTimeoutMs: 100,
    });
    const started = Date.now();
    const res = await request(app).get('/readyz');
    expect(res.status).toBe(503);
    expect(res.body).toEqual({ status: 'db_unavailable' });
    expect(Date.now() - started).toBeLessThan(2000);
  });

  test('/readyz answers 503 shutting_down while shutting down, without pinging', async () => {
    const pingDatabase = vi.fn(() => Promise.resolve());
    const app = createHealthApp({ isShuttingDown: () => true, pingDatabase });
    const res = await request(app).get('/readyz');
    expect(res.status).toBe(503);
    expect(res.body).toEqual({ status: 'shutting_down' });
    expect(pingDatabase).not.toHaveBeenCalled();
  });
});

describe('installGracefulShutdown', { tags: ['@exercise'] }, () => {
  let server: Server;
  let base: string;
  let events: string[];
  let finishSlow: () => void;

  beforeEach(async () => {
    events = [];
    let release: () => void = () => {};
    const released = new Promise<void>((resolve) => (release = resolve));
    finishSlow = release;
    server = createServer((req, res) => {
      if (req.url === '/slow') {
        events.push('slow request started');
        void released.then(() => {
          events.push('slow request finished');
          res.end('done');
        });
      } else if (req.url === '/hang') {
        events.push('hanging request started');
      } else res.end('ok');
    });
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
    base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  });

  afterEach(async () => {
    finishSlow();
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  function install(overrides: Partial<ShutdownDeps> = {}) {
    const signals = new EventEmitter();
    const exit = vi.fn((code: number) => {
      events.push(`exit ${code}`);
    });
    const closeResources = vi.fn(async () => {
      events.push('resources closed');
    });
    const log = vi.fn();
    const deps: ShutdownDeps = { server, exit, closeResources, graceMs: 5000, log, ...overrides };
    const handle = installGracefulShutdown(signals, deps);
    return { signals, exit, closeResources, log, handle, deps };
  }

  test('is not shutting down before a signal', () => {
    const { handle, exit } = install();
    expect(handle.isShuttingDown()).toBe(false);
    expect(exit).not.toHaveBeenCalled();
  });

  test('on SIGTERM it finishes the request in flight, then closes resources, then exits 0', async () => {
    const { signals, exit, closeResources, handle, log } = install();
    const inFlight = fetch(`${base}/slow`).then((res) => res.text());
    await vi.waitFor(() => expect(events).toContain('slow request started'));

    signals.emit('SIGTERM');
    expect(handle.isShuttingDown()).toBe(true);
    expect(log).toHaveBeenCalledWith('SIGTERM received, shutting down');
    await wait(100);
    expect(exit).not.toHaveBeenCalled(); // still serving the request in flight

    finishSlow();
    expect(await inFlight).toBe('done');
    await vi.waitFor(() => expect(exit).toHaveBeenCalledWith(0));
    expect(closeResources).toHaveBeenCalledTimes(1);
    expect(events).toEqual(['slow request started', 'slow request finished', 'resources closed', 'exit 0']);
  });

  test('stops accepting new connections once shutdown starts', async () => {
    const { signals } = install();
    const inFlight = fetch(`${base}/slow`);
    await vi.waitFor(() => expect(events).toContain('slow request started'));
    signals.emit('SIGTERM');
    await wait(50);
    await expect(fetch(`${base}/other`, { headers: { connection: 'close' } })).rejects.toThrow();
    finishSlow();
    await inFlight;
  });

  test('SIGINT (Ctrl+C) shuts down the same way', async () => {
    const { signals, exit, log } = install();
    signals.emit('SIGINT');
    await vi.waitFor(() => expect(exit).toHaveBeenCalledWith(0));
    expect(log).toHaveBeenCalledWith('SIGINT received, shutting down');
  });

  test('a second signal changes nothing - one close, one exit', async () => {
    const { signals, exit, closeResources } = install();
    signals.emit('SIGTERM');
    signals.emit('SIGTERM');
    signals.emit('SIGINT');
    await vi.waitFor(() => expect(exit).toHaveBeenCalled());
    await wait(100);
    expect(exit).toHaveBeenCalledTimes(1);
    expect(exit).toHaveBeenCalledWith(0);
    expect(closeResources).toHaveBeenCalledTimes(1);
  });

  test('exits 1 when closing the resources fails', async () => {
    const { signals, exit } = install({
      closeResources: () => Promise.reject(new Error('pool.end() failed')),
    });
    signals.emit('SIGTERM');
    await vi.waitFor(() => expect(exit).toHaveBeenCalled());
    expect(exit).toHaveBeenCalledTimes(1);
    expect(exit).toHaveBeenCalledWith(1);
  });

  test('forces the exit with code 1 after graceMs when a request never finishes', async () => {
    const { signals, exit, closeResources } = install({ graceMs: 300 });
    const hanging = fetch(`${base}/hang`).then(
      () => 'answered',
      () => 'connection closed',
    );
    await vi.waitFor(() => expect(events).toContain('hanging request started'));
    const started = Date.now();
    signals.emit('SIGTERM');
    await vi.waitFor(() => expect(exit).toHaveBeenCalled(), { timeout: 3000 });
    expect(Date.now() - started).toBeGreaterThanOrEqual(250);
    expect(Date.now() - started).toBeLessThan(2500);
    expect(exit).toHaveBeenCalledTimes(1);
    expect(exit).toHaveBeenCalledWith(1);
    expect(await hanging).toBe('connection closed'); // closeAllConnections destroyed the socket
    await wait(100);
    expect(exit).toHaveBeenCalledTimes(1);
    expect(closeResources.mock.calls.length).toBeLessThanOrEqual(1);
  });
});
