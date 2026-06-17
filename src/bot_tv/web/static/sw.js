const CACHE_NAME = 'bot-tv-v1';
const STATIC_ASSETS = [
  '/',
  '/static/styles.css',
  '/static/app.js',
  '/manifest.json',
  '/static/components/App.js',
  '/static/components/StreamWidget.js',
  '/static/components/api.js',
  '/static/components/chat/ChatTab.js',
  '/static/components/followers/FollowersTab.js',
  '/static/components/agent/AgentTab.js',
  '/static/components/actions/ActionsTab.js',
  '/static/components/actions/UserAutocomplete.js',
  '/static/components/actions/ClipSection.js',
  '/static/components/actions/UserSection.js',
  '/static/components/actions/ModelSection.js',
  '/static/components/actions/DangerSection.js',
  '/static/vendor/preact.module.js',
  '/static/vendor/htm.module.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
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

// Network-first: intenta red, fallback a caché para rutas estáticas.
// Las rutas /api/ y /ws siempre van a la red directamente.
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  if (url.pathname.startsWith('/api/') || url.pathname === '/ws') {
    return; // Sin intercepción
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
