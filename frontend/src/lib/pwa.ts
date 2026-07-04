// PWA utilities for eBay Draft Commander
// Service worker registration is handled automatically by VitePWA

import { useState, useEffect, useCallback, useRef } from 'react'

export interface BeforeInstallPromptEvent extends Event {
    readonly platforms: string[];
    readonly userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
    prompt(): Promise<void>;
}

let updateAvailableCallback: (() => void) | null = null;

// Browsers only recheck sw.js on navigation (and at most ~daily), so an
// installed PWA resumed from memory can run a stale build for days. Nudge
// registration.update() whenever the app regains focus and on a slow interval
// — combined with skipWaiting + the auto-reload in App.tsx, every resume
// picks up the newest build within seconds.
const UPDATE_CHECK_INTERVAL_MS = 30 * 60 * 1000;

export function onUpdateAvailable(callback: () => void) {
    updateAvailableCallback = callback;
    // Listen for VitePWA's update mechanism
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.ready.then((registration) => {
            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                if (newWorker) {
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            console.debug('[PWA] New version available');
                            if (updateAvailableCallback) {
                                updateAvailableCallback();
                            }
                        }
                    });
                }
            });

            const checkForUpdate = () => {
                registration.update().catch(() => { /* offline — retry next trigger */ });
            };
            document.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'visible') checkForUpdate();
            });
            setInterval(checkForUpdate, UPDATE_CHECK_INTERVAL_MS);
        });
    }
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
