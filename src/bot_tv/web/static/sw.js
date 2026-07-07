const CACHE_NAME = '__CACHE_VERSION__';
const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/static/app.js',
  '/static/css/variables.css',
  '/static/css/layout.css',
  '/static/css/buttons.css',
  '/static/css/header.css',
  '/static/css/tabs.css',
  '/static/css/chat.css',
  '/static/css/followers.css',
  '/static/css/agent.css',
  '/static/css/actions.css',
  '/static/css/forms.css',
  '/static/css/settings.css',
  '/static/css/toasts.css',
  '/static/css/modals.css',
  '/static/css/responsive.css',
  '/static/components/App.js',
  '/static/components/StreamWidget.js',
  '/static/components/ToastOverlay.js',
  '/static/components/event-config.js',
  '/static/components/api.js',
  '/static/components/CustomSelect.js',
  '/static/components/chat/ChatTab.js',
  '/static/components/UserAvatar.js',
  '/static/components/followers/FollowersTab.js',
  '/static/components/agent/AgentTab.js',
  '/static/components/settings/SettingsTab.js',
  '/static/components/actions/ActionsTab.js',
  '/static/components/actions/ClipSection.js',
  '/static/components/actions/ModelSection.js',
  '/static/components/actions/DangerSection.js',
  '/static/hooks/useWebSocket.js',
  '/static/lib/preact-setup.js',
  '/static/lib/utils.js',
  '/static/lib/emotes.js',
  '/static/vendor/preact.module.js',
  '/static/vendor/preact-hooks.module.js',
  '/static/vendor/htm.module.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.all(
        STATIC_ASSETS.map(url => {
          return fetch(new Request(url, { cache: 'reload' })).then(response => {
            if (!response.ok) {
              throw new Error(`Request for ${url} failed with status ${response.status}`);
            }
            return cache.put(url, response);
          });
        })
      );
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches
      .keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

// Network-first: intenta red, fallback a caché para rutas estáticas.
// Las rutas /api/ y /ws siempre van a la red directamente.
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Solo interceptar requests del mismo origen
  if (url.origin !== self.location.origin) {
    return;
  }

  if (url.pathname.startsWith('/api/') || url.pathname === '/ws') {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then(response => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
