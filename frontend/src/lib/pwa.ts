// PWA utilities for eBay Draft Commander
// Service worker registration is handled automatically by VitePWA

import { useState, useEffect, useCallback, useRef } from 'react'

export interface BeforeInstallPromptEvent extends Event {
    readonly platforms: string[];
    readonly userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
    prompt(): Promise<void>;
}

// Browsers only recheck sw.js on navigation (and at most ~daily), so an
// installed PWA resumed from memory can run a stale build for days. We nudge
// registration.update() on focus + a slow interval so the newest build is
// *fetched* in the background. It then installs as a waiting SW and activates
// on the NEXT launch (sw.ts drops skipWaiting) — the running page is never
// reloaded. Silent updates, no mid-task interruption.
const UPDATE_CHECK_INTERVAL_MS = 30 * 60 * 1000;

export function checkForUpdatesInBackground() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.ready.then((registration) => {
        const checkForUpdate = () => {
            registration.update().catch(() => { /* offline — retry next trigger */ });
        };
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') checkForUpdate();
        });
        setInterval(checkForUpdate, UPDATE_CHECK_INTERVAL_MS);
    });
}

// PWA Install Prompt
export function usePWAInstall() {
    const [isInstallable, setIsInstallable] = useState(false)
    const deferredPromptRef = useRef<BeforeInstallPromptEvent | null>(null)

    useEffect(() => {
        const handler = (e: Event) => {
            e.preventDefault()
            deferredPromptRef.current = e as BeforeInstallPromptEvent
            setIsInstallable(true)
            console.debug('[PWA] Install prompt available')
        }

        window.addEventListener('beforeinstallprompt', handler)
        return () => window.removeEventListener('beforeinstallprompt', handler)
    }, [])

    const promptInstall = useCallback(async () => {
        if (!deferredPromptRef.current) {
            console.debug('[PWA] Install prompt not available')
            return false
        }

        deferredPromptRef.current.prompt()
        const { outcome } = await deferredPromptRef.current.userChoice
        console.debug(`[PWA] User response: ${outcome}`)

        deferredPromptRef.current = null
        setIsInstallable(false)

        return outcome === 'accepted'
    }, [])

    return { promptInstall, isInstallable }
}

// Check if app is installed
export function isAppInstalled(): boolean {
    // Check if running in standalone mode (installed PWA)
    return window.matchMedia('(display-mode: standalone)').matches ||
        (window.navigator as Navigator & { standalone?: boolean }).standalone ||
        document.referrer.includes('android-app://');
}

// Check if running on mobile
export function isMobileDevice(): boolean {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent
    );
}
