// SVOJ Money -- offline app-shell cache.
// Bump CACHE_NAME (e.g. v1 -> v2) whenever index.html/icons/manifest change,
// so returning visitors pick up the new version instead of a stale cached copy.
const CACHE_NAME = 'svoj-money-shell-v1';
const SHELL_FILES = [
  './',
  './index.html',
  './money-manifest.webmanifest',
  './money-icon-32.png',
  './money-icon-180.png',
  './money-icon-192.png',
  './money-icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Only the app shell is cached here. Everything else -- Supabase API calls,
  // the supabase-js CDN script -- goes straight to the network untouched, so
  // auth/cloud sync always sees live data and is never served a stale response.
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request)
        .then((response) => {
          if (response && response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => cached);
      // Cache-first for instant offline loads, but a fresh copy is fetched in
      // the background and stored for next time whenever a connection exists.
      return cached || network;
    })
  );
});
