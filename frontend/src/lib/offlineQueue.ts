import { useState, useEffect, useCallback } from 'react'

// ─── Online Status ────────────────────────────────────────────

/**
 * React hook that returns real-time online/offline status
 * and a count of pending background sync requests.
 */
export function useOnlineStatus() {
    const [isOnline, setIsOnline] = useState(navigator.onLine)
    const [pendingCount, setPendingCount] = useState(0)
    const [lastSyncUrl, setLastSyncUrl] = useState<string | null>(null)

    useEffect(() => {
        const goOnline = () => setIsOnline(true)
        const goOffline = () => setIsOnline(false)

        window.addEventListener('online', goOnline)
        window.addEventListener('offline', goOffline)

        return () => {
            window.removeEventListener('online', goOnline)
            window.removeEventListener('offline', goOffline)
        }
    }, [])

    // Listen for background sync success messages from the service worker
    useEffect(() => {
        if (!('serviceWorker' in navigator)) return

        const handleMessage = (event: MessageEvent) => {
            if (event.data?.type === 'BACKGROUND_SYNC_SUCCESS') {
                setLastSyncUrl(event.data.url)
                setPendingCount((prev) => Math.max(0, prev - 1))
                // Auto-clear after 3 seconds
                setTimeout(() => setLastSyncUrl(null), 3000)
            }
        }

        navigator.serviceWorker.addEventListener('message', handleMessage)
        return () => {
            navigator.serviceWorker.removeEventListener('message', handleMessage)
        }
    }, [])

    // Track pending mutations when going offline
    const trackPendingRequest = useCallback(() => {
        setPendingCount((prev) => prev + 1)
    }, [])

    return { isOnline, pendingCount, lastSyncUrl, trackPendingRequest }
}

/**
 * Check if the network is currently available
 */
export function isOnline(): boolean {
    return navigator.onLine
}

// ─── Offline-Aware Fetch ──────────────────────────────────────

/**
 * Wraps a fetch call to gracefully handle offline state.
 * When offline, the service worker's BackgroundSyncPlugin will 
 * automatically queue the request and replay it when back online.
 * 
 * This wrapper adds UI feedback — it doesn't change the actual
 * sync behavior (that's in sw.ts).
 */
export async function offlineFetch(
    input: RequestInfo | URL,
    init?: RequestInit,
    options?: {
        onQueued?: () => void
        onSyncSuccess?: () => void
    }
): Promise<Response> {
    const method = init?.method?.toUpperCase() ?? 'GET'
    const isMutation = ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)

    try {
        const response = await fetch(input, init)
        return response
    } catch (error) {
        if (!navigator.onLine && isMutation) {
            // The SW BackgroundSyncPlugin will handle queuing + replay.
            // Notify the caller that it was queued.
            console.debug('[Offline] Request queued for background sync:', input)
            options?.onQueued?.()

            // Return a synthetic response so callers don't crash
            return new Response(
                JSON.stringify({
                    success: true,
                    queued: true,
                    message: 'Saved offline — will sync when connection returns',
                }),
                {
                    status: 202,
                    headers: { 'Content-Type': 'application/json' },
                }
            )
        }

        // Re-throw if online (genuine network error)
        throw error
    }
}
