// Service worker do MapaSP. JS puro, sem build step: o placeholder __BUILD__
// é trocado pelo timestamp do build no plugin `serviceWorkerBuildId` de
// vite.config.ts, então o nome dos caches versionados muda a cada deploy.
const BUILD = "__BUILD__";
const SHELL_CACHE = `mapasp-shell-${BUILD}`;
const ASSET_CACHE = `mapasp-assets-${BUILD}`;
const API_CACHE = "mapasp-api";
const VERSIONED_PREFIXES = ["mapasp-shell-", "mapasp-assets-"];
const SHELL_URL = "/index.html";

const NEVER_CACHE_PREFIXES = [
  "/api/admin",
  "/api/events",
  "/api/auth",
  "/api/contacts",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      try {
        await cache.add(SHELL_URL);
      } catch {
        // Sem rede na instalação: o fallback fica pendente até o próximo sucesso.
      }
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((name) => {
            const isVersioned = VERSIONED_PREFIXES.some((prefix) => name.startsWith(prefix));
            const isCurrent = name === SHELL_CACHE || name === ASSET_CACHE;
            return isVersioned && !isCurrent;
          })
          .map((name) => caches.delete(name)),
      );
      await self.clients.claim();
    })(),
  );
});

function withCacheHeader(response) {
  const headers = new Headers(response.headers);
  headers.set("X-From-Cache", "1");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function networkFirstNavigate(request) {
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(SHELL_CACHE);
      cache.put(SHELL_URL, response.clone());
    }
    return response;
  } catch {
    const cache = await caches.open(SHELL_CACHE);
    const cached = await cache.match(SHELL_URL);
    if (cached) return cached;
    return new Response("Offline e sem snapshot em cache.", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
}

async function cacheFirstAsset(request) {
  const cache = await caches.open(ASSET_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) cache.put(request, response.clone());
  return response;
}

// Stale-while-revalidate para as camadas do mapa: tenta a rede para manter o
// cache atualizado e, se a rede falhar, responde com o último snapshot em
// cache marcado com o header X-From-Cache para a UI mostrar o aviso.
async function apiStaleWhileRevalidate(request) {
  const cache = await caches.open(API_CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) return withCacheHeader(cached);
    return new Response(JSON.stringify({ error: "offline" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (NEVER_CACHE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigate(request));
    return;
  }

  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(cacheFirstAsset(request));
    return;
  }

  if (url.pathname === "/api/layers" || url.pathname.startsWith("/api/layers/")) {
    event.respondWith(apiStaleWhileRevalidate(request));
  }
});
