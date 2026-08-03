// Minimal service worker: exists only to satisfy PWA installability.
// No caching (avoids stale assets / offline complexity the app doesn't need).
self.addEventListener('fetch', () => {});
