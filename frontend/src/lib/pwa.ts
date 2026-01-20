// Service Worker Registration for PWA
let updateAvailableCallback: (() => void) | null = null;

export function onUpdateAvailable(callback: () => void) {
    updateAvailableCallback = callback;
}

export function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker
                .register('/sw.js')
                .then((registration) => {
                    console.log('[PWA] Service Worker registered:', registration.scope);

                    // Check for updates every hour
                    setInterval(() => {
                        registration.update();
                    }, 60 * 60 * 1000);

                    // Listen for new service worker
                    registration.addEventListener('updatefound', () => {
                        const newWorker = registration.installing;
                        if (newWorker) {
                            newWorker.addEventListener('statechange', () => {
                                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                    console.log('[PWA] New version available');
                                    if (updateAvailableCallback) {
                                        updateAvailableCallback();
                                    }
                                }
                            });
                        }
                    });
                })
                .catch((error) => {
                    console.error('[PWA] Service Worker registration failed:', error);
                });
        });
    }
}

// PWA Install Prompt
export function usePWAInstall() {
    let deferredPrompt: any = null;

    window.addEventListener('beforeinstallprompt', (e) => {
        // Prevent the mini-infobar from appearing on mobile
        e.preventDefault();
        // Stash the event so it can be triggered later
        deferredPrompt = e;

        console.log('[PWA] Install prompt available');
    });

    const promptInstall = async () => {
        if (!deferredPrompt) {
            console.log('[PWA] Install prompt not available');
            return false;
        }

        // Show the install prompt
        deferredPrompt.prompt();

        // Wait for the user to respond to the prompt
        const { outcome } = await deferredPrompt.userChoice;

        console.log(`[PWA] User response: ${outcome}`);

        // Clear the deferredPrompt
        deferredPrompt = null;

        return outcome === 'accepted';
    };

    const isInstallable = () => !!deferredPrompt;

    return { promptInstall, isInstallable };
}

// Check if app is installed
export function isAppInstalled(): boolean {
    // Check if running in standalone mode (installed PWA)
    return window.matchMedia('(display-mode: standalone)').matches ||
        (window.navigator as any).standalone ||
        document.referrer.includes('android-app://');
}

// Check if running on mobile
export function isMobileDevice(): boolean {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent
    );
}
