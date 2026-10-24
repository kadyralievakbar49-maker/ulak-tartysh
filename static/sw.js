const CACHE_NAME = 'ulak-tartysh-v66';
const PRECACHE_URLS = [
  '/static/css/style.css?v=64',
  '/static/css/portal.css?v=1',
  '/static/js/main.js?v=54',
  '/static/js/i18n.js?v=52',
  '/static/js/media.js?v=2',
  '/static/js/album.js',
  '/static/js/portal.js?v=1',
  '/static/js/translations.js?v=56',
  '/static/img/logo.jpg',
  '/static/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const requestUrl = new URL(event.request.url);
  if (requestUrl.origin !== self.location.origin) return;
  if (/^\/(profile|admin|api|forgot-password|reset-password|confirm-email)(\/|$)/.test(requestUrl.pathname)) {
    event.respondWith(fetch(event.request));
    return;
  }

  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok && !/private|no-store/.test(response.headers.get('Cache-Control') || '')) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => caches.match(event.request).then((cached) => cached || new Response(
          '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Улак тартыш</title><p>Интернет байланышын текшериңиз.</p><p>Проверьте подключение к интернету.</p><p>Check your internet connection.</p>',
          { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
        )))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;

      return fetch(event.request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          if (response.ok) {
            cache.put(event.request, copy);
          }
        });
        return response;
      }).catch(() => Response.error());
    })
  );
});
