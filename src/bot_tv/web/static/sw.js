// Service Worker minimalista (sin caché) para mantener la instalabilidad PWA.
// APP_VERSION se reemplaza en el build (vite.config.js) con la versión de package.json:
// cada release cambia los bytes de este archivo, el navegador lo detecta, instala el
// nuevo SW y 'activate' elimina las cachés que no pertenezcan a la versión vigente.
const APP_VERSION = '__APP_VERSION__';
const CACHE_PREFIX = 'bot-tv-';
const CURRENT_CACHE = `${CACHE_PREFIX}${APP_VERSION}`;

async function purgeOutdatedCaches() {
  const names = await caches.keys();
  await Promise.all(
    names
      .filter(name => name.startsWith(CACHE_PREFIX) && name !== CURRENT_CACHE)
      .map(name => caches.delete(name))
  );
}

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event =>
  event.waitUntil(purgeOutdatedCaches().then(() => self.clients.claim()))
);
