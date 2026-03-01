// PWA utilities for eBay Draft Commander
// Service worker registration is handled automatically by VitePWA

let updateAvailableCallback: (() => void) | null = null;

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
                            console.log('[PWA] New version available');
                            if (updateAvailableCallback) {
                                updateAvailableCallback();
                            }
                        }
                    });
                }
            });
        });
    }
}

// PWA Install Prompt
export function usePWAInstall() {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
        (window.navigator as Navigator & { standalone?: boolean }).standalone ||
        document.referrer.includes('android-app://');
}

// Check if running on mobile
export function isMobileDevice(): boolean {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent
    );
}
