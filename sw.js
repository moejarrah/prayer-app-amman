const CACHE = "prayer-times-v5";
const STATIC_FILES = ["./", "./index.html", "./manifest.json", "./prayers-data.js", "./icon-192.png", "./icon-512.png", "./apple-touch-icon.png"];
const STATIC_PATHS = new Set(
  STATIC_FILES
    .filter(file => file !== "./")
    .map(file => new URL(file, self.registration.scope).pathname)
);
const DATA_PATH = new URL("./prayers-data.js", self.registration.scope).pathname;

self.addEventListener("install", e => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC_FILES))
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;

  const url = new URL(e.request.url);

  if (e.request.mode === "navigate") {
    e.respondWith(
      caches.match("./index.html").then(cached => {
        const networkFetch = fetch(e.request).then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put("./index.html", clone));
          return res;
        }).catch(() => cached);
        return networkFetch;
      })
    );
    return;
  }

  if (url.origin === self.location.origin && url.pathname === DATA_PATH) {
    e.respondWith(
      fetch(e.request).then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return res;
      }).catch(() => caches.match(e.request))
    );
    return;
  }

  if (url.origin === self.location.origin && STATIC_PATHS.has(url.pathname)) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        const networkFetch = fetch(e.request).then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
          return res;
        }).catch(() => cached);
        return cached || networkFetch;
      })
    );
    return;
  }

  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
