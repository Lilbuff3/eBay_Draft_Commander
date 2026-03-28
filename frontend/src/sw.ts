/// <reference lib="webworker" />
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching'
import { registerRoute, NavigationRoute } from 'workbox-routing'
import { NetworkFirst, StaleWhileRevalidate, CacheFirst } from 'workbox-strategies'
import { BackgroundSyncPlugin } from 'workbox-background-sync'
import { CacheableResponsePlugin } from 'workbox-cacheable-response'
import { ExpirationPlugin } from 'workbox-expiration'

declare let self: ServiceWorkerGlobalScope

// ─── Precaching ───────────────────────────────────────────────
// VitePWA injects the build-time asset manifest here automatically
cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)

// ─── Offline Fallback ─────────────────────────────────────────
// Serve offline.html when a navigation request fails
const offlineFallback = new NavigationRoute(
    new NetworkFirst({
        cacheName: 'pages-cache',
        plugins: [
            new CacheableResponsePlugin({ statuses: [200] }),
        ],
    }),
    {
        // Don't match /api/ routes — those are data, not pages
    }
)

// Add offline page to cache on install, then register the fallback
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open('pages-cache').then((cache) => {
            return cache.addAll(['/offline.html'])
        })
    )
    self.skipWaiting()
})

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim())
})

registerRoute(offlineFallback)

// ─── API GET Requests: NetworkFirst ───────────────────────────
// Short cache (5 min) — stale API data causes "eBay Offline" and empty job lists.
// Only serves from cache when genuinely offline (networkTimeoutSeconds fallback).
registerRoute(
    ({ url, request }) =>
        url.pathname.startsWith('/api/') && request.method === 'GET',
    new NetworkFirst({
        cacheName: 'api-cache',
        networkTimeoutSeconds: 3,
        plugins: [
            new CacheableResponsePlugin({ statuses: [200] }),
            new ExpirationPlugin({
                maxEntries: 50,
                maxAgeSeconds: 5 * 60, // 5 minutes — API data goes stale fast
            }),
        ],
    })
)

// ─── Background Sync for POST/PUT/DELETE ──────────────────────
// Failed mutation requests are queued in IndexedDB and replayed
// when the browser regains connectivity.
const bgSyncPlugin = new BackgroundSyncPlugin('offline-mutations', {
    maxRetentionTime: 24 * 60, // retry for up to 24 hours (minutes)
    onSync: async ({ queue }) => {
        let entry
        while ((entry = await queue.shiftRequest())) {
            try {
                await fetch(entry.request.clone())
                console.debug('[SW] Background Sync: replayed', entry.request.url)

                // Notify all clients that a sync happened
                const clients = await self.clients.matchAll({ type: 'window' })
                for (const client of clients) {
                    client.postMessage({
                        type: 'BACKGROUND_SYNC_SUCCESS',
                        url: entry.request.url,
                    })
                }
            } catch (error) {
                console.error('[SW] Background Sync replay failed:', error)
                await queue.unshiftRequest(entry)
                throw error // Stops the loop — browser will retry later
            }
        }
    },
})

// Queue failed POST/PUT/DELETE requests to /api/
registerRoute(
    ({ url, request }) =>
        url.pathname.startsWith('/api/') &&
        ['POST', 'PUT', 'DELETE'].includes(request.method),
    new NetworkFirst({
        cacheName: 'api-mutations',
        plugins: [bgSyncPlugin],
    }),
    'POST'
)

registerRoute(
    ({ url, request }) =>
        url.pathname.startsWith('/api/') &&
        ['POST', 'PUT', 'DELETE'].includes(request.method),
    new NetworkFirst({
        cacheName: 'api-mutations',
        plugins: [bgSyncPlugin],
    }),
    'PUT'
)

registerRoute(
    ({ url, request }) =>
        url.pathname.startsWith('/api/') &&
        ['POST', 'PUT', 'DELETE'].includes(request.method),
    new NetworkFirst({
        cacheName: 'api-mutations',
        plugins: [bgSyncPlugin],
    }),
    'DELETE'
)

// ─── Image Caching: StaleWhileRevalidate ──────────────────────
registerRoute(
    ({ request }) => request.destination === 'image',
    new StaleWhileRevalidate({
        cacheName: 'image-cache',
        plugins: [
            new CacheableResponsePlugin({ statuses: [200] }),
            new ExpirationPlugin({
                maxEntries: 200,
                maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
            }),
        ],
    })
)

// ─── Static Assets: CacheFirst ────────────────────────────────
registerRoute(
    ({ request }) =>
        request.destination === 'style' ||
        request.destination === 'script' ||
        request.destination === 'font',
    new CacheFirst({
        cacheName: 'static-assets',
        plugins: [
            new CacheableResponsePlugin({ statuses: [200] }),
            new ExpirationPlugin({
                maxEntries: 100,
                maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
            }),
        ],
    })
)

// ─── Push Notifications (stub) ────────────────────────────────
self.addEventListener('push', (event) => {
    const data = event.data?.json() ?? {}
    const title = data.title || 'eBay Draft Commander'
    const options: NotificationOptions = {
        body: data.body || 'New notification',
        icon: '/icons/icon-192.png',
        badge: '/icons/icon-192.png',
        data: data.url,
    }

    event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
    event.notification.close()

    if (event.notification.data) {
        event.waitUntil(self.clients.openWindow(event.notification.data))
    }
})
