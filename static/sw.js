// Service worker for Altiico Catalog: offline cache for content-hashed
// static data files.
//
// Caching strategy:
//   - Content-hashed JSON (collections.*.json): cache-first, indefinite. The
//     filename changes when content changes, so a cached copy is always
//     valid for its filename.
//   - build-info.json: network-first, fall back to cache. This is the
//     pointer to the hashed files and must be fresh; offline falls back to
//     the last known pointer.
//   - App shell (index.html, app.css, app.js, sw.js): network-first with an
//     offline cache fallback.
//   - Everything else: pass through to network, no caching.
//
// The cache is versioned by CACHE_VERSION. Bump and the install step purges
// old caches.

// Stamped by scripts/build_catalog.py on every build. Never edit by hand.
const CACHE_VERSION = '2a27b0d5cfd4';
const CACHE_NAME = `altiico-${CACHE_VERSION}`;
const APP_SHELL = [
  './',
  './index.html',
  './app.css',
  './app.js',
];

// Content-hashed data files match these patterns. The hash is the 12-hex
// segment before .json (see scripts/build_catalog.py).
const HASHED_JSON = /\/data\/collections\.[0-9a-f]{12}\.json$/;
const BUILD_INFO = /\/data\/build-info\.json$/;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) =>
        (key.startsWith('altiico-') || key.startsWith('superyeti-')) && key !== CACHE_NAME
      ).map((key) => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Content-hashed JSON: cache-first, indefinite.
  if (HASHED_JSON.test(url.pathname)) {
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((c) => c.put(req, copy));
        return resp;
      }))
    );
    return;
  }

  // build-info.json: network-first, fall back to cache.
  if (BUILD_INFO.test(url.pathname)) {
    event.respondWith(
      fetch(req).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((c) => c.put(req, copy));
        return resp;
      }).catch(() => caches.match(req))
    );
    return;
  }

  // App shell: network-first. Cache is the offline fallback only.
  const isAppShell = url.origin === self.location.origin &&
    (url.pathname === './' || url.pathname === '/' ||
     APP_SHELL.includes('./' + url.pathname.replace(/^\//, '')));
  if (isAppShell) {
    event.respondWith(
      fetch(req).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((c) => c.put(req, copy));
        return resp;
      }).catch(() => caches.match(req))
    );
    return;
  }

  // Everything else: pass through.
});

// Allow the page to trigger an immediate update.
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') self.skipWaiting();
});
