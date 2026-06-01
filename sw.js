const CACHE = "prayer-times-v10";
const FILES = [
  "./",
  "./index.html",
  "./sw.js",
  "./manifest.json",
  "./prayers-data.js",
  "./icon-192.png",
  "./icon-512.png",
  "./apple-touch-icon.png"
];

self.addEventListener("install", event => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(FILES)));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(event.request).then(cached => {
      const fetchPromise = fetch(event.request).then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => {
        if (cached) return cached;
        if (event.request.mode === "navigate") {
          return caches.match("./index.html").then(index => index || caches.match("./"));
        }
        return new Response("", { status: 504, statusText: "Offline" });
      });

      return cached || fetchPromise;
    })
  );
});
