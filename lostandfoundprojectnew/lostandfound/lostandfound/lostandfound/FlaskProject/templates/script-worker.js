self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('lostfound-cache-v1').then((cache) => {
      return cache.addAll([
        '/',
        '/manifest.json',
        '/static/uploads/',
      ]);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
