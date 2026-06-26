import { useState, useEffect } from 'react'
import { getSettings, saveSettings, softRestart } from '@/lib/api'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2, Save, RefreshCw, Zap } from 'lucide-react'

export function Settings() {
    const [settings, setSettings] = useState<Record<string, string>>({})
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [restarting, setRestarting] = useState(false)

    useEffect(() => {
        loadSettings()
    }, [])

    async function loadSettings() {
        try {
            const data = await getSettings()
            setSettings(data)
        } catch (error) {
            toast.error('Failed to load settings')
            console.error(error)
        } finally {
            setLoading(false)
        }
    }

    async function handleSave() {
        setSaving(true)
        try {
            const result = await saveSettings(settings)
            if (result.success) {
                toast.success('Settings saved successfully')
            } else {
                toast.error(result.error || 'Failed to save')
            }
        } catch {
            toast.error('Error saving settings')
        } finally {
            setSaving(false)
        }
    }

    const handleChange = (key: string, value: string) => {
        setSettings(prev => ({ ...prev, [key]: value }))
    }

    async function handleRestart() {
        if (!confirm("Are you sure you want to reboot the backend? Current operations may be interrupted.")) return
        setRestarting(true)
        try {
            await softRestart()
            toast.info("Reboot command sent. Waiting for server to come back...")

            // Wait 3 seconds then start polling
            setTimeout(pollHeartbeat, 3000)
        } catch {
            toast.error("Failed to trigger reboot")
            setRestarting(false)
        }
    }

    async function pollHeartbeat() {
        let attempts = 0
        const maxAttempts = 15

        const check = async () => {
            try {
                const res = await fetch('/api/system/health')
                if (res.ok) {
                    toast.success("Server is back online!")
                    // Small delay to ensure everything is ready
                    setTimeout(() => window.location.reload(), 1000)
                    return
                }
            } catch {
                // Ignore connection errors during reboot
            }

            if (attempts < maxAttempts) {
                attempts++
                setTimeout(check, 1000)
            } else {
                toast.error("Server took too long to respond. Please check the terminal manually.")
                setRestarting(false)
            }
        }

        check()
    }

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center text-stone-500">
                <Loader2 className="h-8 w-8 animate-spin mr-2" />
                Loading configuration…
            </div>
        )
    }

    return (
        <div className="h-full overflow-auto bg-transparent p-6">
            <div className="mx-auto max-w-4xl space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div>
                        <h1 className="text-2xl font-display font-bold text-ink-800 tracking-tight text-balance">Settings</h1>
                        <p className="text-stone-500 text-sm">Configure API keys and application defaults</p>
                    </div>
                    <Button onClick={handleSave} disabled={saving} className="w-full sm:w-auto">
                        {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                        Save Changes
                    </Button>
                </div>

                <Tabs defaultValue="ebay-policies" className="w-full">
                    <TabsList className="w-full bg-white p-1 shadow-sm rounded-lg border border-stone-200 flex overflow-x-auto">
                        <TabsTrigger value="ebay-policies" className="flex-1 min-w-0 text-xs sm:text-sm">
                            <span className="hidden sm:inline">eBay Policies</span>
                            <span className="sm:hidden">Policies</span>
                        </TabsTrigger>
                        <TabsTrigger value="ebay-auth" className="flex-1 min-w-0 text-xs sm:text-sm">
                            <span className="hidden sm:inline">eBay Authentication</span>
                            <span className="sm:hidden">Auth</span>
                        </TabsTrigger>
                        <TabsTrigger value="automation" className="flex-1 min-w-0 text-xs sm:text-sm">
                            <span className="hidden sm:inline">Automation</span>
                            <span className="sm:hidden"><Zap className="h-4 w-4" /></span>
                        </TabsTrigger>
                        <TabsTrigger value="ai" className="flex-1 min-w-0 text-xs sm:text-sm">
                            <span className="hidden sm:inline">AI & Other</span>
                            <span className="sm:hidden">AI</span>
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="ebay-policies" className="mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>Listing Policies</CardTitle>
                                <CardDescription>Default policies applied to new listings (IDs found in eBay Business Policies)</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="fulfill">Fulfillment Policy ID (Shipping)</Label>
                                    <Input
                                        id="fulfill"
                                        value={settings['EBAY_FULFILLMENT_POLICY'] || ''}
                                        onChange={e => handleChange('EBAY_FULFILLMENT_POLICY', e.target.value)}
                                        placeholder="e.g. 1234567890"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="payment">Payment Policy ID</Label>
                                    <Input
                                        id="payment"
                                        value={settings['EBAY_PAYMENT_POLICY'] || ''}
                                        onChange={e => handleChange('EBAY_PAYMENT_POLICY', e.target.value)}
                                        placeholder="e.g. 1234567890"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="return">Return Policy ID</Label>
                                    <Input
                                        id="return"
                                        value={settings['EBAY_RETURN_POLICY'] || ''}
                                        onChange={e => handleChange('EBAY_RETURN_POLICY', e.target.value)}
                                        placeholder="e.g. 1234567890"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="location">Merchant Location Key</Label>
                                    <Input
                                        id="location"
                                        value={settings['EBAY_MERCHANT_LOCATION'] || ''}
                                        onChange={e => handleChange('EBAY_MERCHANT_LOCATION', e.target.value)}
                                        placeholder="e.g. US_CA_SAN_JOSE"
                                    />
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    <TabsContent value="ebay-auth" className="mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>eBay API Credentials</CardTitle>
                                <CardDescription>Application keys from eBay Developer Portal</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="appid">App ID (Client ID)</Label>
                                    <Input
                                        id="appid"
                                        value={settings['EBAY_APP_ID'] || ''}
                                        onChange={e => handleChange('EBAY_APP_ID', e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="certid">Cert ID (Client Secret)</Label>
                                    <Input
                                        id="certid"
                                        type="password"
                                        value={settings['EBAY_CERT_ID'] || ''}
                                        onChange={e => handleChange('EBAY_CERT_ID', e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="runame">RuName (Redirect URL Name)</Label>
                                    <Input
                                        id="runame"
                                        value={settings['EBAY_RUNAME'] || ''}
                                        onChange={e => handleChange('EBAY_RUNAME', e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="token">User Refresh Token</Label>
                                    <Input
                                        id="token"
                                        type="password"
                                        className="font-mono text-xs"
                                        value={settings['EBAY_USER_TOKEN'] || ''}
                                        onChange={e => handleChange('EBAY_USER_TOKEN', e.target.value)}
                                        placeholder="v^1.1..."
                                    />
                                </div>
                                <div className="flex items-center space-x-2 pt-2">
                                    <Label>Environment:</Label>
                                    <div className="flex space-x-4">
                                        <label className="flex items-center space-x-2 cursor-pointer">
                                            <input
                                                type="radio"
                                                name="env"
                                                checked={settings['EBAY_ENVIRONMENT'] !== 'sandbox'}
                                                onChange={() => handleChange('EBAY_ENVIRONMENT', 'production')}
                                            />
                                            <span>Production</span>
                                        </label>
                                        <label className="flex items-center space-x-2 cursor-pointer">
                                            <input
                                                type="radio"
                                                name="env"
                                                checked={settings['EBAY_ENVIRONMENT'] === 'sandbox'}
                                                onChange={() => handleChange('EBAY_ENVIRONMENT', 'sandbox')}
                                            />
                                            <span>Sandbox</span>
                                        </label>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    <TabsContent value="automation" className="mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>Auto-Publish</CardTitle>
                                <CardDescription>
                                    When enabled, listings that meet all criteria will publish directly to eBay without manual review.
                                    Items below the confidence threshold or minimum price will still go to the Review Queue.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="flex items-center justify-between p-4 bg-stone-50 rounded-lg border">
                                    <div>
                                        <Label htmlFor="auto-publish" className="text-base font-medium">Auto-Publish Enabled</Label>
                                        <p className="text-sm text-stone-500 mt-1">
                                            {settings['AUTO_PUBLISH'] === 'true'
                                                ? 'High-confidence listings will publish automatically'
                                                : 'All listings require manual approval'}
                                        </p>
                                    </div>
                                    <button
                                        id="auto-publish"
                                        type="button"
                                        role="switch"
                                        aria-checked={settings['AUTO_PUBLISH'] === 'true'}
                                        onClick={() => handleChange('AUTO_PUBLISH', settings['AUTO_PUBLISH'] === 'true' ? 'false' : 'true')}
                                        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                                            settings['AUTO_PUBLISH'] === 'true' ? 'bg-emerald-600' : 'bg-stone-300'
                                        }`}
                                    >
                                        <span
                                            className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg transform transition-transform ${
                                                settings['AUTO_PUBLISH'] === 'true' ? 'translate-x-5' : 'translate-x-0'
                                            }`}
                                        />
                                    </button>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="confidence">Confidence Threshold (%)</Label>
                                    <div className="flex items-center gap-4">
                                        <Input
                                            id="confidence"
                                            type="number"
                                            min="0"
                                            max="100"
                                            className="w-24"
                                            value={settings['CONFIDENCE_THRESHOLD'] || '85'}
                                            onChange={e => handleChange('CONFIDENCE_THRESHOLD', e.target.value)}
                                        />
                                        <span className="text-sm text-stone-500">
                                            AI must be at least {settings['CONFIDENCE_THRESHOLD'] || '85'}% confident to auto-publish
                                        </span>
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="min-price">Minimum Price ($)</Label>
                                    <div className="flex items-center gap-4">
                                        <Input
                                            id="min-price"
                                            type="number"
                                            min="0"
                                            step="0.01"
                                            className="w-24"
                                            value={settings['AUTO_PUBLISH_MIN_PRICE'] || '15.00'}
                                            onChange={e => handleChange('AUTO_PUBLISH_MIN_PRICE', e.target.value)}
                                        />
                                        <span className="text-sm text-stone-500">
                                            Items priced below this go to Review Queue for manual check
                                        </span>
                                    </div>
                                </div>

                                <div className="flex items-center justify-between p-4 bg-stone-50 rounded-lg border">
                                    <div>
                                        <Label htmlFor="fast-mode" className="text-base font-medium">Fast Mode</Label>
                                        <p className="text-sm text-stone-500 mt-1">
                                            {settings['FAST_MODE'] === 'true'
                                                ? 'Skipping web research — 5–13s faster per item'
                                                : 'Full pipeline: Phase 2 web research + Gemini price grounding enabled'}
                                        </p>
                                    </div>
                                    <button
                                        id="fast-mode"
                                        type="button"
                                        role="switch"
                                        aria-checked={settings['FAST_MODE'] === 'true'}
                                        onClick={() => handleChange('FAST_MODE', settings['FAST_MODE'] === 'true' ? 'false' : 'true')}
                                        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                                            settings['FAST_MODE'] === 'true' ? 'bg-emerald-600' : 'bg-stone-300'
                                        }`}
                                    >
                                        <span
                                            className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg transform transition-transform ${
                                                settings['FAST_MODE'] === 'true' ? 'translate-x-5' : 'translate-x-0'
                                            }`}
                                        />
                                    </button>
                                </div>

                                <div className="flex items-center justify-between p-4 bg-stone-50 rounded-lg border">
                                    <div className="flex-1 pr-6">
                                        <Label htmlFor="promoted-listings" className="text-base font-medium">Promoted Listings</Label>
                                        <p className="text-sm text-stone-500 mt-1">
                                            {settings['PROMOTED_LISTINGS_ENABLED'] === 'true'
                                                ? 'New listings will automatically be promoted at the ad rate below'
                                                : 'Promoted Listings disabled'}
                                        </p>
                                        
                                        {settings['PROMOTED_LISTINGS_ENABLED'] === 'true' && (
                                            <div className="mt-4 flex items-center gap-4">
                                                <div className="flex items-center">
                                                    <Input
                                                        id="ad-rate"
                                                        type="number"
                                                        min="0"
                                                        max="100"
                                                        step="0.1"
                                                        className="w-24 rounded-r-none border-r-0"
                                                        value={settings['PROMOTED_LISTINGS_AD_RATE'] || '5.0'}
                                                        onChange={e => handleChange('PROMOTED_LISTINGS_AD_RATE', e.target.value)}
                                                    />
                                                    <div className="flex items-center justify-center h-10 px-3 bg-stone-100 border border-input rounded-r-md text-stone-500 select-none">
                                                        %
                                                    </div>
                                                </div>
                                                <Label htmlFor="ad-rate" className="text-sm font-normal text-stone-500">
                                                    Ad Rate (Bid Percentage)
                                                </Label>
                                            </div>
                                        )}
                                    </div>
                                    <button
                                        id="promoted-listings"
                                        type="button"
                                        role="switch"
                                        aria-checked={settings['PROMOTED_LISTINGS_ENABLED'] === 'true'}
                                        onClick={() => handleChange('PROMOTED_LISTINGS_ENABLED', settings['PROMOTED_LISTINGS_ENABLED'] === 'true' ? 'false' : 'true')}
                                        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer self-start rounded-full border-2 border-transparent transition-colors ${
                                            settings['PROMOTED_LISTINGS_ENABLED'] === 'true' ? 'bg-emerald-600' : 'bg-stone-300'
                                        }`}
                                    >
                                        <span
                                            className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg transform transition-transform ${
                                                settings['PROMOTED_LISTINGS_ENABLED'] === 'true' ? 'translate-x-5' : 'translate-x-0'
                                            }`}
                                        />
                                    </button>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    <TabsContent value="ai" className="mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>AI Configuration</CardTitle>
                                <CardDescription>API Keys for AI Analysis</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="google_key">Google Gemini API Key</Label>
                                    <Input
                                        id="google_key"
                                        type="password"
                                        value={settings['GOOGLE_API_KEY'] || ''}
                                        onChange={e => handleChange('GOOGLE_API_KEY', e.target.value)}
                                        placeholder="AIza..."
                                    />
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="border-red-100 shadow-sm mt-6">
                            <CardHeader>
                                <CardTitle className="text-red-700">System Controls</CardTitle>
                                <CardDescription>Advanced actions for the application host.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="flex flex-col gap-3">
                                    <p className="text-sm text-stone-500">
                                        If the backend server is behaving unexpectedly, you can trigger a soft reboot.
                                        The app will become unavailable for a few seconds while the process restarts.
                                    </p>
                                    <Button
                                        variant="destructive"
                                        onClick={handleRestart}
                                        disabled={restarting}
                                        className="w-full sm:w-auto"
                                    >
                                        {restarting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                                        Reboot Backend Server
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    )
}
