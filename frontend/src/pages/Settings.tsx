import { useState, useEffect } from 'react'
import { getSettings, saveSettings } from '@/lib/api'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2, Save } from 'lucide-react'

export function Settings() {
    const [settings, setSettings] = useState<Record<string, string>>({})
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)

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
        } catch (error) {
            toast.error('Error saving settings')
        } finally {
            setSaving(false)
        }
    }

    const handleChange = (key: string, value: string) => {
        setSettings(prev => ({ ...prev, [key]: value }))
    }

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center text-stone-500">
                <Loader2 className="h-8 w-8 animate-spin mr-2" />
                Loading configuration...
            </div>
        )
    }

    return (
        <div className="h-full overflow-auto bg-stone-50 p-6">
            <div className="mx-auto max-w-4xl space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-stone-800">Settings</h1>
                        <p className="text-stone-500">Configure API keys and application defaults</p>
                    </div>
                    <Button onClick={handleSave} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700">
                        {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                        Save Changes
                    </Button>
                </div>

                <Tabs defaultValue="ebay-policies" className="w-full">
                    <TabsList className="grid w-full grid-cols-3 bg-white p-1 shadow-sm rounded-lg border border-stone-200">
                        <TabsTrigger value="ebay-policies">eBay Policies</TabsTrigger>
                        <TabsTrigger value="ebay-auth">eBay Authentication</TabsTrigger>
                        <TabsTrigger value="ai">AI & Other</TabsTrigger>
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
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    )
}
