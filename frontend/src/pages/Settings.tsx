import { useState, useEffect } from 'react'
import { fetchWithKey, getSettings, saveSettings, softRestart } from '@/lib/api'
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
                const res = await fetchWithKey('/api/system/health')
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
            <div className="mx-auto max-w-4xl space-y-6 pb-24">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div>
                        <h1 className="text-2xl font-display font-bold text-white tracking-tight text-balance">Settings</h1>
                        <p className="text-slate-450 text-sm">Configure API keys and application defaults</p>
                    </div>
                    <Button onClick={handleSave} disabled={saving} className="w-full sm:w-auto bg-brand-500 hover:bg-brand-600 text-white shadow-glow">
                        {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin text-white" /> : <Save className="mr-2 h-4 w-4" />}
                        Save Changes
                    </Button>
                </div>

                <Tabs defaultValue="ebay-policies" className="w-full">
                    <TabsList className="w-full bg-slate-950/40 p-1 rounded-xl border border-white/10 flex overflow-x-auto">
                        <TabsTrigger value="ebay-policies" className="flex-1 min-w-0 text-xs sm:text-sm data-[state=active]:bg-slate-800 data-[state=active]:text-brand-400">
                            <span className="hidden sm:inline">eBay Policies</span>
                            <span className="sm:hidden">Policies</span>
                        </TabsTrigger>
                        <TabsTrigger value="ebay-auth" className="flex-1 min-w-0 text-xs sm:text-sm data-[state=active]:bg-slate-800 data-[state=active]:text-brand-400">
                            <span className="hidden sm:inline">eBay Authentication</span>
                            <span className="sm:hidden">Auth</span>
                        </TabsTrigger>
                        <TabsTrigger value="automation" className="flex-1 min-w-0 text-xs sm:text-sm data-[state=active]:bg-slate-800 data-[state=active]:text-brand-400">
                            <span className="hidden sm:inline">Automation</span>
                            <span className="sm:hidden"><Zap className="h-4 w-4" /></span>
                        </TabsTrigger>
                        <TabsTrigger value="ai" className="flex-1 min-w-0 text-xs sm:text-sm data-[state=active]:bg-slate-800 data-[state=active]:text-brand-400">
                            <span className="hidden sm:inline">AI & Other</span>
                            <span className="sm:hidden">AI</span>
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="ebay-policies" className="mt-6">
                        <Card className="bg-slate-900/40 border-white/5 shadow-glass backdrop-blur-2xl rounded-3xl">
                            <CardHeader>
                                <CardTitle className="text-white font-bold font-display">Listing Policies</CardTitle>
                                <CardDescription className="text-slate-400">Default policies applied to new listings (IDs found in eBay Business Policies)</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="fulfill" className="text-slate-200">Fulfillment Policy ID (Shipping)</Label>
                                    <Input
                                        id="fulfill"
                                        className="bg-slate-950/40 border-white/10 text-white placeholder-slate-600 focus-visible:ring-brand-500/50"
                                        value={settings['EBAY_FULFILLMENT_POLICY'] || ''}
                                        onChange={e => handleChange('EBAY_FULFILLMENT_POLICY', e.target.value)}
                                        placeholder="e.g. 1234567890"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="payment" className="text-slate-200">Payment Policy ID</Label>
                                    <Input
                                        id="payment"
                                        className="bg-slate-950/40 border-white/10 text-white placeholder-slate-600 focus-visible:ring-brand-500/50"
                                        value={settings['EBAY_PAYMENT_POLICY'] || ''}
                                        onChange={e => handleChange('EBAY_PAYMENT_POLICY', e.target.value)}
                                        placeholder="e.g. 1234567890"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="return" className="text-slate-200">Return Policy ID</Label>
                                    <Input
                                        id="return"
                                        className="bg-slate-950/40 border-white/10 text-white placeholder-slate-600 focus-visible:ring-brand-500/50"
                                        value={settings['EBAY_RETURN_POLICY'] || ''}
                                        onChange={e => handleChange('EBAY_RETURN_POLICY', e.target.value)}
                                        placeholder="e.g. 1234567890"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="location" className="text-slate-200">Merchant Location Key</Label>
                                    <Input
                                        id="location"
                                        className="bg-slate-950/40 border-white/10 text-white placeholder-slate-600 focus-visible:ring-brand-500/50"
                                        value={settings['EBAY_MERCHANT_LOCATION'] || ''}
                                        onChange={e => handleChange('EBAY_MERCHANT_LOCATION', e.target.value)}
                                        placeholder="e.g. US_CA_SAN_JOSE"
                                    />
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    <TabsContent value="ebay-auth" className="mt-6">
                        <Card className="bg-slate-900/40 border-white/5 shadow-glass backdrop-blur-2xl rounded-3xl">
                            <CardHeader>
                                <CardTitle className="text-white font-bold font-display">eBay API Credentials</CardTitle>
                                <CardDescription className="text-slate-400">Application keys from eBay Developer Portal</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="appid" className="text-slate-200">App ID (Client ID)</Label>
                                    <Input
                                        id="appid"
                                        className="bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                        value={settings['EBAY_APP_ID'] || ''}
                                        onChange={e => handleChange('EBAY_APP_ID', e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="certid" className="text-slate-200">Cert ID (Client Secret)</Label>
                                    <Input
                                        id="certid"
                                        type="password"
                                        className="bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                        value={settings['EBAY_CERT_ID'] || ''}
                                        onChange={e => handleChange('EBAY_CERT_ID', e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="runame" className="text-slate-200">RuName (Redirect URL Name)</Label>
                                    <Input
                                        id="runame"
                                        className="bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                        value={settings['EBAY_RUNAME'] || ''}
                                        onChange={e => handleChange('EBAY_RUNAME', e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="token" className="text-slate-200">User Refresh Token</Label>
                                    <Input
                                        id="token"
                                        type="password"
                                        className="font-mono text-xs bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                        value={settings['EBAY_USER_TOKEN'] || ''}
                                        onChange={e => handleChange('EBAY_USER_TOKEN', e.target.value)}
                                        placeholder="v^1.1..."
                                    />
                                </div>
                                <div className="flex items-center space-x-2 pt-2">
                                    <Label className="text-slate-200">Environment:</Label>
                                    <div className="flex space-x-4">
                                        <label className="flex items-center space-x-2 cursor-pointer text-slate-400 hover:text-white">
                                            <input
                                                type="radio"
                                                name="env"
                                                className="accent-brand-500"
                                                checked={settings['EBAY_ENVIRONMENT'] !== 'sandbox'}
                                                onChange={() => handleChange('EBAY_ENVIRONMENT', 'production')}
                                            />
                                            <span>Production</span>
                                        </label>
                                        <label className="flex items-center space-x-2 cursor-pointer text-slate-400 hover:text-white">
                                            <input
                                                type="radio"
                                                name="env"
                                                className="accent-brand-500"
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
                        <Card className="bg-slate-900/40 border-white/5 shadow-glass backdrop-blur-2xl rounded-3xl">
                            <CardHeader>
                                <CardTitle className="text-white font-bold font-display">Auto-Publish</CardTitle>
                                <CardDescription className="text-slate-400">
                                    When enabled, listings that meet all criteria will publish directly to eBay without manual review.
                                    Items below the confidence threshold or minimum price will still go to the Review Queue.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="flex items-center justify-between p-4 bg-slate-950/40 border border-white/5 rounded-2xl">
                                    <div>
                                        <Label htmlFor="auto-publish" className="text-base font-medium text-slate-200">Auto-Publish Enabled</Label>
                                        <p className="text-sm text-slate-500 mt-1">
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
                                            settings['AUTO_PUBLISH'] === 'true' ? 'bg-emerald-600' : 'bg-slate-800'
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
                                    <Label htmlFor="confidence" className="text-slate-200">Confidence Threshold (%)</Label>
                                    <div className="flex items-center gap-4">
                                        <Input
                                            id="confidence"
                                            type="number"
                                            min="0"
                                            max="100"
                                            className="w-24 bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                            value={settings['CONFIDENCE_THRESHOLD'] || '85'}
                                            onChange={e => handleChange('CONFIDENCE_THRESHOLD', e.target.value)}
                                        />
                                        <span className="text-sm text-slate-500">
                                            AI must be at least {settings['CONFIDENCE_THRESHOLD'] || '85'}% confident to auto-publish
                                        </span>
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="min-price" className="text-slate-200">Minimum Price ($)</Label>
                                    <div className="flex items-center gap-4">
                                        <Input
                                            id="min-price"
                                            type="number"
                                            min="0"
                                            step="0.01"
                                            className="w-24 bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                            value={settings['AUTO_PUBLISH_MIN_PRICE'] || '15.00'}
                                            onChange={e => handleChange('AUTO_PUBLISH_MIN_PRICE', e.target.value)}
                                        />
                                        <span className="text-sm text-slate-500">
                                            Items priced below this go to Review Queue for manual check
                                        </span>
                                    </div>
                                </div>

                                <div className="flex items-center justify-between p-4 bg-slate-950/40 border border-white/5 rounded-2xl">
                                    <div>
                                        <Label htmlFor="fast-mode" className="text-base font-medium text-slate-200">Fast Mode</Label>
                                        <p className="text-sm text-slate-500 mt-1">
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
                                            settings['FAST_MODE'] === 'true' ? 'bg-emerald-600' : 'bg-slate-800'
                                        }`}
                                    >
                                        <span
                                            className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg transform transition-transform ${
                                                settings['FAST_MODE'] === 'true' ? 'translate-x-5' : 'translate-x-0'
                                            }`}
                                        />
                                    </button>
                                </div>

                                <div className="flex items-center justify-between p-4 bg-slate-950/40 border border-white/5 rounded-2xl">
                                    <div className="flex-1 pr-6">
                                        <Label htmlFor="promoted-listings" className="text-base font-medium text-slate-200">Promoted Listings</Label>
                                        <p className="text-sm text-slate-500 mt-1">
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
                                                        className="w-24 rounded-r-none border-r-0 bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                                        value={settings['PROMOTED_LISTINGS_AD_RATE'] || '5.0'}
                                                        onChange={e => handleChange('PROMOTED_LISTINGS_AD_RATE', e.target.value)}
                                                    />
                                                    <div className="flex items-center justify-center h-10 px-3 bg-slate-950/60 border border-white/10 rounded-r-md text-slate-500 select-none">
                                                        %
                                                    </div>
                                                </div>
                                                <Label htmlFor="ad-rate" className="text-sm font-normal text-slate-500">
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
                                            settings['PROMOTED_LISTINGS_ENABLED'] === 'true' ? 'bg-emerald-600' : 'bg-slate-800'
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

                        <Card className="bg-slate-900/40 border-white/5 shadow-glass backdrop-blur-2xl rounded-3xl mt-6">
                            <CardHeader>
                                <CardTitle className="text-white font-bold font-display">Sourcing Verdicts</CardTitle>
                                <CardDescription className="text-slate-400">
                                    Buy/pass math for the Source tab. Max buy price = the lower of
                                    (net proceeds − min profit) and (net proceeds ÷ ROI multiple).
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="sourcing-min-profit" className="text-slate-200">Minimum Profit ($)</Label>
                                    <div className="flex items-center gap-4">
                                        <Input
                                            id="sourcing-min-profit"
                                            type="number"
                                            min="0"
                                            step="0.50"
                                            className="w-24 bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                            value={settings['SOURCING_MIN_PROFIT'] || '5.00'}
                                            onChange={e => handleChange('SOURCING_MIN_PROFIT', e.target.value)}
                                        />
                                        <span className="text-sm text-slate-500">Smallest profit worth your time per item</span>
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="sourcing-roi" className="text-slate-200">ROI Multiple (×)</Label>
                                    <div className="flex items-center gap-4">
                                        <Input
                                            id="sourcing-roi"
                                            type="number"
                                            min="0"
                                            step="0.5"
                                            className="w-24 bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                            value={settings['SOURCING_ROI_MULTIPLE'] || '3.0'}
                                            onChange={e => handleChange('SOURCING_ROI_MULTIPLE', e.target.value)}
                                        />
                                        <span className="text-sm text-slate-500">3 = classic "pay at most a third of net" rule. 0 disables.</span>
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="sourcing-ship" className="text-slate-200">Est. Shipping Cost ($)</Label>
                                    <div className="flex items-center gap-4">
                                        <Input
                                            id="sourcing-ship"
                                            type="number"
                                            min="0"
                                            step="0.50"
                                            className="w-24 bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                            value={settings['SOURCING_SHIP_COST'] || '5.00'}
                                            onChange={e => handleChange('SOURCING_SHIP_COST', e.target.value)}
                                        />
                                        <span className="text-sm text-slate-500">Actual cost to ship a sourced item (Media Mail ≈ $4–5)</span>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    <TabsContent value="ai" className="mt-6">
                        <Card className="bg-slate-900/40 border-white/5 shadow-glass backdrop-blur-2xl rounded-3xl">
                            <CardHeader>
                                <CardTitle className="text-white font-bold font-display">AI Configuration</CardTitle>
                                <CardDescription className="text-slate-400">API Keys for AI Analysis</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="google_key" className="text-slate-200">Google Gemini API Key</Label>
                                    <Input
                                        id="google_key"
                                        type="password"
                                        className="bg-slate-950/40 border-white/10 text-white focus-visible:ring-brand-500/50"
                                        value={settings['GOOGLE_API_KEY'] || ''}
                                        onChange={e => handleChange('GOOGLE_API_KEY', e.target.value)}
                                        placeholder="AIza..."
                                    />
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="border-rose-500/20 bg-rose-500/5 shadow-glass backdrop-blur-2xl rounded-3xl mt-6">
                            <CardHeader>
                                <CardTitle className="text-rose-300 font-bold font-display">System Controls</CardTitle>
                                <CardDescription className="text-rose-400">Advanced actions for the application host.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="flex flex-col gap-3">
                                    <p className="text-sm text-rose-300">
                                        If the backend server is behaving unexpectedly, you can trigger a soft reboot.
                                        The app will become unavailable for a few seconds while the process restarts.
                                    </p>
                                    <Button
                                        variant="destructive"
                                        onClick={handleRestart}
                                        disabled={restarting}
                                        className="w-full sm:w-auto bg-rose-650 hover:bg-rose-700 text-white"
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
