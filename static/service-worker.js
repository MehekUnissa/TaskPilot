const CACHE_NAME = "taskpilot-v1";

const STATIC_FILES = [
    "/static/css/style.css",
    "/static/manifest.json",
    "/static/icon.svg"
];

self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache =>
            cache.addAll(STATIC_FILES)
        )
    );

    self.skipWaiting();
});

self.addEventListener("activate", event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            )
        )
    );

    self.clients.claim();
});

self.addEventListener("fetch", event => {
    const url = new URL(event.request.url);

    if (
        event.request.method !== "GET" ||
        url.origin !== self.location.origin ||
        !url.pathname.startsWith("/static/")
    ) {
        return;
    }

    event.respondWith(
        caches.match(event.request).then(cached => {
            return cached || fetch(event.request);
        })
    );
});