var CACHE = "borajunto-v2";
var OFFLINE_URL = "/offline/";
var PRECACHE = [
    OFFLINE_URL,
    "/static/images/icons/icon-192.png",
    "/static/images/logo/borajunto-symbol.svg",
];

self.addEventListener("install", function (event) {
    event.waitUntil(
        caches
            .open(CACHE)
            .then(function (cache) {
                return cache.addAll(PRECACHE);
            })
            .then(function () {
                return self.skipWaiting();
            }),
    );
});

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches
            .keys()
            .then(function (nomes) {
                return Promise.all(
                    nomes
                        .filter(function (nome) {
                            return nome !== CACHE;
                        })
                        .map(function (nome) {
                            return caches.delete(nome);
                        }),
                );
            })
            .then(function () {
                return self.clients.claim();
            }),
    );
});

self.addEventListener("fetch", function (event) {
    var request = event.request;
    var url = new URL(request.url);
    // POSTs
    if (request.method !== "GET" || url.origin !== location.origin) {
        return;
    }

    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request).catch(function () {
                return caches.match(OFFLINE_URL);
            }),
        );
        return;
    }

    // Arquivos estáticos: busca sempre a versão nova na rede e guarda uma cópia;
    // a cópia guardada só é usada quando não há conexão.
    if (url.pathname.startsWith("/static/")) {
        event.respondWith(
            fetch(request)
                .then(function (resposta) {
                    if (resposta.ok) {
                        var copia = resposta.clone();
                        caches.open(CACHE).then(function (cache) {
                            cache.put(request, copia);
                        });
                    }
                    return resposta;
                })
                .catch(function () {
                    return caches.match(request);
                }),
        );
    }
});
