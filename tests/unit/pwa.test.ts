import { readFileSync } from 'node:fs';
import { act, renderHook } from '@testing-library/preact';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { precachePaths, serviceWorkerSource } from '../../src/pwa/precache';
import {
  applyUpdate,
  dismissOfflineStatus,
  registerServiceWorker,
  resetOfflineStatus,
  useOfflineStatus,
} from '../../src/pwa/register';

describe('precachePaths', () => {
  it('keeps the app files, sorted, and leaves out the worker, source maps and the practice shop', () => {
    expect(
      precachePaths([
        'index.html',
        'sw.js',
        'assets/b.js',
        'assets/b.js.map',
        'shop/index.html',
        'assets/a.css',
      ]),
    ).toEqual(['assets/a.css', 'assets/b.js', 'index.html']);
  });
});

describe('serviceWorkerSource', () => {
  const template = readFileSync('src/pwa/service-worker.js', 'utf8');
  it('fills the version and the precache list into the real template', () => {
    const source = serviceWorkerSource(template, ['index.html', 'assets/a.js'], 'abc123');
    expect(source).toContain(`const VERSION = "abc123";`);
    expect(source).toContain(`const PRECACHE = ["index.html","assets/a.js"];`);
    expect(source).not.toMatch(/__VERSION__|__PRECACHE__/);
  });
  it('refuses a template without its placeholders', () => {
    expect(() => serviceWorkerSource('self.addEventListener("fetch", () => {})', [], 'v')).toThrow(
      /placeholder/,
    );
  });
});

/** Just enough of the ServiceWorker API to drive register.ts. */
class FakeWorker extends EventTarget {
  state = 'installing';
  postMessage = vi.fn();
  become(state: string) {
    this.state = state;
    this.dispatchEvent(new Event('statechange'));
  }
}

function fakeContainer(active: FakeWorker | null) {
  const registration = Object.assign(new EventTarget(), {
    active,
    installing: null as FakeWorker | null,
    waiting: null as FakeWorker | null,
    update: vi.fn(() => Promise.resolve()),
  });
  const container = Object.assign(new EventTarget(), {
    controller: active,
    register: vi.fn(() => Promise.resolve(registration)),
  });
  const install = () => {
    const worker = new FakeWorker();
    registration.installing = worker;
    registration.dispatchEvent(new Event('updatefound'));
    worker.become('installed');
    return worker;
  };
  return { container: container as unknown as ServiceWorkerContainer, registration, install };
}

describe('registerServiceWorker', () => {
  afterEach(() => resetOfflineStatus());

  it('reports "ready" once the first version is installed, and the message can be dismissed', async () => {
    const { container, install } = fakeContainer(null);
    const { result } = renderHook(() => useOfflineStatus());
    await act(() => registerServiceWorker(container, vi.fn()));
    expect(result.current).toBe('none');
    act(() => void install());
    expect(result.current).toBe('ready');
    act(() => dismissOfflineStatus());
    expect(result.current).toBe('none');
  });

  it('reports an update, and reloads only after the learner applies it and the new version takes over', async () => {
    const reload = vi.fn();
    const { container, install } = fakeContainer(new FakeWorker());
    const { result } = renderHook(() => useOfflineStatus());
    await act(() => registerServiceWorker(container, reload));
    let next!: FakeWorker;
    act(() => {
      next = install();
    });
    expect(result.current).toBe('update');

    container.dispatchEvent(new Event('controllerchange'));
    expect(reload).not.toHaveBeenCalled();

    act(() => applyUpdate());
    expect(next.postMessage).toHaveBeenCalledWith({ type: 'SKIP_WAITING' });
    container.dispatchEvent(new Event('controllerchange'));
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('finds a version that was already waiting when the page loaded', async () => {
    const { container, registration } = fakeContainer(new FakeWorker());
    registration.waiting = new FakeWorker();
    const { result } = renderHook(() => useOfflineStatus());
    await act(() => registerServiceWorker(container, vi.fn()));
    expect(result.current).toBe('update');
  });

  it('keeps the app working when registration fails', async () => {
    const { container } = fakeContainer(null);
    vi.mocked(container.register).mockRejectedValueOnce(new Error('insecure context'));
    await expect(registerServiceWorker(container, vi.fn())).resolves.toBeUndefined();
  });
});
