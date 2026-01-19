import { useState, useEffect } from 'react'
import { Phone, Download, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { isMobileDevice, isAppInstalled } from '@/lib/pwa'

export function PWAInstallBanner() {
    const [showBanner, setShowBanner] = useState(false)
    const [deferredPrompt, setDeferredPrompt] = useState<any>(null)

    useEffect(() => {
        // Don't show if already installed
        if (isAppInstalled()) {
            return
        }

        // Listen for install prompt
        const handler = (e: Event) => {
            e.preventDefault()
            setDeferredPrompt(e)

            // Show banner after 5 seconds on mobile
            if (isMobileDevice()) {
                setTimeout(() => setShowBanner(true), 5000)
            }
        }

        window.addEventListener('beforeinstallprompt', handler)

        return () => {
            window.removeEventListener('beforeinstallprompt', handler)
        }
    }, [])

    const handleInstall = async () => {
        if (!deferredPrompt) return

        deferredPrompt.prompt()
        const { outcome } = await deferredPrompt.userChoice

        console.log(`User response: ${outcome}`)
        setDeferredPrompt(null)
        setShowBanner(false)
    }

    if (!showBanner || !deferredPrompt) {
        return null
    }

    return (
        <Card className="fixed bottom-20 left-4 right-4 p-4 bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-2xl z-50 md:max-w-sm md:left-auto md:right-4">
            <button
                onClick={() => setShowBanner(false)}
                className="absolute top-2 right-2 p-1 rounded-full hover:bg-white/20"
            >
                <X size={16} />
            </button>

            <div className="flex items-start gap-3">
                <div className="p-2 bg-white/20 rounded-lg">
                    <Phone size={24} />
                </div>

                <div className="flex-1">
                    <h3 className="font-semibold mb-1">Install App</h3>
                    <p className="text-sm text-white/90 mb-3">
                        Add Draft Commander to your home screen for quick access
                    </p>

                    <Button
                        onClick={handleInstall}
                        size="sm"
                        className="bg-white text-blue-600 hover:bg-white/90"
                    >
                        <Download size={16} className="mr-2" />
                        Install
                    </Button>
                </div>
            </div>
        </Card>
    )
}
