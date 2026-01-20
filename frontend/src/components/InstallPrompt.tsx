import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Download, X, Share, PlusSquare } from 'lucide-react'

interface BeforeInstallPromptEvent extends Event {
    prompt: () => Promise<void>
    userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export function InstallPrompt() {
    const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
    const [isInstalled, setIsInstalled] = useState(false)
    const [dismissed, setDismissed] = useState(false)
    const [isIOS, setIsIOS] = useState(false)

    useEffect(() => {
        // Check if already installed
        if (window.matchMedia('(display-mode: standalone)').matches) {
            setIsInstalled(true)
            return
        }

        // Detect iOS
        const userAgent = window.navigator.userAgent.toLowerCase()
        const isIosDevice = /iphone|ipad|ipod/.test(userAgent)
        setIsIOS(isIosDevice)

        // Listen for install prompt (Android/Desktop)
        const handler = (e: Event) => {
            e.preventDefault()
            setDeferredPrompt(e as BeforeInstallPromptEvent)
        }

        window.addEventListener('beforeinstallprompt', handler)

        // Listen for successful install
        window.addEventListener('appinstalled', () => {
            setIsInstalled(true)
            setDeferredPrompt(null)
        })

        return () => {
            window.removeEventListener('beforeinstallprompt', handler)
        }
    }, [])

    const handleInstall = async () => {
        if (!deferredPrompt) return

        deferredPrompt.prompt()
        const { outcome } = await deferredPrompt.userChoice

        if (outcome === 'accepted') {
            setDeferredPrompt(null)
        }
    }

    const handleDismiss = () => {
        setDismissed(true)
    }

    // Don't show if installed or dismissed
    if (isInstalled || dismissed) {
        return null
    }

    // iOS Prompt
    if (isIOS) {
        return (
            <AnimatePresence>
                <motion.div
                    initial={{ opacity: 0, y: 50 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 50 }}
                    className="fixed bottom-4 left-4 right-4 bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-2xl z-50 md:max-w-md md:left-auto md:right-8"
                >
                    <div className="flex justify-between items-start mb-2">
                        <h3 className="text-white font-semibold text-sm">Install App</h3>
                        <button onClick={handleDismiss} className="text-slate-400 hover:text-white">
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                    <p className="text-slate-300 text-xs mb-3">
                        Install this app on your iPhone:
                        <br />
                        1. Tap <Share className="w-3 h-3 inline mx-1" /> <strong>Share</strong>
                        <br />
                        2. Scroll down and tap <PlusSquare className="w-3 h-3 inline mx-1" /> <strong>Add to Home Screen</strong>
                    </p>
                </motion.div>
            </AnimatePresence>
        )
    }

    // Android/Desktop Prompt
    if (!deferredPrompt) {
        return null
    }

    return (
        <AnimatePresence>
            <motion.button
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                onClick={handleInstall}
                className="fixed bottom-20 left-1/2 -translate-x-1/2 flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-full shadow-lg hover:bg-blue-700 transition-colors z-50"
            >
                <Download className="w-4 h-4" />
                Install App
                <div
                    onClick={(e) => {
                        e.stopPropagation()
                        handleDismiss()
                    }}
                    className="ml-1 p-0.5 hover:bg-blue-500 rounded-full cursor-pointer"
                >
                    <X className="w-3 h-3" />
                </div>
            </motion.button>
        </AnimatePresence>
    )
}
