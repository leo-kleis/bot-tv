// Service Worker ligero para instalabilidad PWA y caché segura de assets estáticos versionados.
// APP_VERSION se reemplaza en el build (vite.config.js) con la versión de package.json:
// cada release cambia los bytes de este archivo, el navegador instala el nuevo SW y
// 'activate' elimina las cachés que no pertenezcan a la versión vigente.
const APP_VERSION = '__APP_VERSION__';
const CACHE_PREFIX = 'bot-tv-';
const CURRENT_CACHE = `${CACHE_PREFIX}${APP_VERSION}`;
const STATIC_ASSET_PREFIXES = ['/static/assets/', '/static/icons/', '/icons/'];

async function purgeOutdatedCaches() {
  const names = await caches.keys();
  await Promise.all(
    names
      .filter(name => name.startsWith(CACHE_PREFIX) && name !== CURRENT_CACHE)
      .map(name => caches.delete(name))
  );
}

function isSafeStaticRequest(request) {
  if (request.method !== 'GET' || request.mode === 'navigate') {
    return false;
  }
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return false;
  }
  if (url.searchParams.has('token')) {
    return false;
  }
  if (url.pathname.startsWith('/api/') || url.pathname === '/ws') {
    return false;
  }
  if (url.pathname.startsWith('/static/assets/') && url.pathname.endsWith('.json')) {
    return false;
  }
  return STATIC_ASSET_PREFIXES.some(prefix => url.pathname.startsWith(prefix));
}

async function cacheFirstAsset(request) {
  try {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
  } catch {
    // Continuar con red si la lectura de caché falla
  }

  const response = await fetch(request);
  const contentType = (response.headers.get('content-type') || '').toLowerCase();
  const isCacheable =
    response.status === 200 &&
    response.type === 'basic' &&
    !response.redirected &&
    !contentType.includes('text/html');

  if (isCacheable) {
    try {
      const cache = await caches.open(CURRENT_CACHE);
      await cache.put(request, response.clone());
    } catch {
      // Ignorar errores de cuota al escribir en caché
    }
  }

  return response;
}

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event =>
  event.waitUntil(purgeOutdatedCaches().then(() => self.clients.claim()))
);
self.addEventListener('fetch', event => {
  if (!isSafeStaticRequest(event.request)) {
    return;
  }
  event.respondWith(cacheFirstAsset(event.request));
});
