// Service Worker minimalista (sin caché) para mantener la instalabilidad PWA.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
