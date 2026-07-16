import { useEffect, useState } from 'react'
import { Download, Check, Share, PlusSquare, Smartphone } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { usePWAInstall, isAppInstalled, isMobileDevice } from '@/lib/pwa'

// A discoverable, always-reachable "Install app" entry for Settings — a native
// app lets you find install/about in settings, not just via a transient banner.
// Reuses the shared pwa.ts helpers; the floating InstallPrompt still handles the
// opportunistic banner elsewhere.
export function InstallCard() {
    const { promptInstall, isInstallable } = usePWAInstall()
    const [installed, setInstalled] = useState(() => isAppInstalled())
    const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent)

    useEffect(() => {
        const onInstalled = () => setInstalled(true)
        window.addEventListener('appinstalled', onInstalled)
        return () => window.removeEventListener('appinstalled', onInstalled)
    }, [])

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-ink-800 font-bold font-display flex items-center gap-2">
                    <Smartphone className="h-5 w-5 text-persimmon-600" />
                    App
                </CardTitle>
                <CardDescription>
                    Install Draft Commander to your home screen so it opens fullscreen, like a native app.
                </CardDescription>
            </CardHeader>
            <CardContent>
                {installed ? (
                    <div className="flex items-center gap-2 text-sm text-emerald-700">
                        <Check className="h-4 w-4" />
                        Installed — running as an app.
                    </div>
                ) : isInstallable ? (
                    <Button
                        onClick={() => { void promptInstall() }}
                        className="bg-persimmon-600 hover:bg-persimmon-700 text-white shadow-sm"
                    >
                        <Download className="mr-2 h-4 w-4" />
                        Install app
                    </Button>
                ) : isIOS ? (
                    <div className="text-sm text-stone-600 leading-relaxed">
                        On iPhone: tap <Share className="inline h-3.5 w-3.5 mx-0.5" /> <strong>Share</strong>,
                        then <PlusSquare className="inline h-3.5 w-3.5 mx-0.5" /> <strong>Add to Home Screen</strong>.
                    </div>
                ) : (
                    <div className="text-sm text-stone-600 leading-relaxed">
                        {isMobileDevice()
                            ? 'Open your browser menu and choose “Install app” or “Add to Home Screen”.'
                            : 'Use your browser’s install icon in the address bar to install this app.'}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
