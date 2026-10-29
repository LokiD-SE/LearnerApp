/*
 * LearnerApp's service worker. vite.config.ts fills in VERSION and PRECACHE at build time and writes the
 * result to dist/sw.js (see src/pwa/precache.ts). It makes the app work offline after the first visit:
 *
 * - install: download every file of this build into a cache named after the build. Hashed files that an
 *   earlier version already cached are copied across instead of downloaded again.
 * - fetch: answer the app's own requests from that cache (page loads get index.html - the app routes with
 *   the URL hash), and fall back to the network for anything not cached.
 * - the practice shop (shop/) is an automation target, so its requests are never touched.
 * - a new version waits until the app asks it to take over (the "Reload" banner), so a page never mixes
 *   files from two builds; activate then deletes the older caches.
 */
const VERSION = '__VERSION__';
const PRECACHE = __PRECACHE__;
const CACHE = `learnerapp-${VERSION}`;
const PREFIX = 'learnerapp-';

const scope = () => new URL(self.registration.scope);
const inScope = (path) => new URL(path, self.registration.scope).href;

self.addEventListener('install', (event) => {
  event.waitUntil(precache());
});

async function precache() {
  const cache = await caches.open(CACHE);
  await Promise.all(
    PRECACHE.map(async (path) => {
      const url = inScope(path);
      const previous = path.startsWith('assets/') ? await caches.match(url) : undefined;
      if (previous) return cache.put(url, previous);
      const response = await fetch(url, { cache: 'no-cache' });
      if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
      return cache.put(url, response);
    }),
  );
}

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names.filter((n) => n.startsWith(PREFIX) && n !== CACHE).map((n) => caches.delete(n)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  const base = scope();
  if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) return;
  if (url.pathname.startsWith(`${base.pathname}shop/`)) return;
  const key = request.mode === 'navigate' ? inScope('index.html') : request;
  event.respondWith(fromCache(key, request));
});

async function fromCache(key, request) {
  const cache = await caches.open(CACHE);
  // ignoreVary: the files never vary, but servers may still send "Vary: Origin", and module scripts
  // are requested with an Origin header that the precache requests did not have.
  return (await cache.match(key, { ignoreSearch: true, ignoreVary: true })) ?? fetch(request);
}
