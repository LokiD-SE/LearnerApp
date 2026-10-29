import { useEffect, useState } from 'preact/hooks';

/**
 * Registers the service worker (production builds only) and tells the UI when the app becomes usable
 * offline or a new version is waiting. A new version takes over only when the learner chooses "Reload",
 * so a page never runs on a mix of files from two builds.
 */
export type OfflineStatus = 'none' | 'ready' | 'update';

let status: OfflineStatus = 'none';
let waiting: ServiceWorker | null = null;
let reloadOnChange = false;
const listeners = new Set<() => void>();

function setStatus(next: OfflineStatus): void {
  status = next;
  listeners.forEach((listener) => listener());
}

export function registerServiceWorker(
  container: ServiceWorkerContainer = navigator.serviceWorker,
  reload: () => void = () => location.reload(),
): Promise<void> {
  container.addEventListener('controllerchange', () => {
    if (reloadOnChange) {
      reloadOnChange = false;
      reload();
    }
  });
  return container
    .register('./sw.js')
    .then((registration) => {
      // With no active version yet this is the first install, which activates by itself; otherwise the
      // new version waits for the learner.
      const onInstalled = (worker: ServiceWorker) => {
        if (!registration.active || registration.active === worker) return setStatus('ready');
        waiting = worker;
        setStatus('update');
      };
      if (registration.waiting && registration.active) onInstalled(registration.waiting);
      registration.addEventListener('updatefound', () => {
        const worker = registration.installing;
        worker?.addEventListener('statechange', () => {
          if (worker.state === 'installed') onInstalled(worker);
        });
      });
      // An installed app can stay open for days without a page load; look for a new version on return.
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') registration.update().catch(() => undefined);
      });
    })
    .catch(() => undefined); // offline support is an extra: the app works without it
}

/** Asks the waiting version to take over; the page reloads once it has. */
export function applyUpdate(): void {
  if (!waiting) return;
  reloadOnChange = true;
  waiting.postMessage({ type: 'SKIP_WAITING' });
}

export function dismissOfflineStatus(): void {
  if (status === 'ready') setStatus('none');
}

export function useOfflineStatus(): OfflineStatus {
  const [current, setCurrent] = useState(status);
  useEffect(() => {
    const listener = () => setCurrent(status);
    listeners.add(listener);
    listener();
    return () => {
      listeners.delete(listener);
    };
  }, []);
  return current;
}

/** For tests: forget everything this module has seen. */
export function resetOfflineStatus(): void {
  status = 'none';
  waiting = null;
  reloadOnChange = false;
  listeners.clear();
}
