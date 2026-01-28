import { useState, useEffect } from 'react'
import { AlertCircle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { sanitizeDescription } from '@/lib/sanitizer'
import { toast } from 'sonner'
import { MediaManager } from './MediaManager'
import type { Listing } from '../ActiveListings'

interface EditListingDialogProps {
    listing: Listing
    isOpen: boolean
    onClose: () => void
    onSave: (sku: string, updates: any) => Promise<void>
}

export function EditListingDialog({ listing, isOpen, onClose, onSave }: EditListingDialogProps) {
    const [title, setTitle] = useState(listing.title)
    const [price, setPrice] = useState(listing.price.toString())
    const [quantity, setQuantity] = useState(listing.availableQuantity.toString())
    const [description, setDescription] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const [media, setMedia] = useState<any[]>([])

    // Fetch full details (description) on open
    useEffect(() => {
        if (isOpen) {
            // Reset basic fields
            setTitle(listing.title)
            setPrice(listing.price.toString())
            setQuantity(listing.availableQuantity.toString())
            setError(null)
            setDescription('Loading description...')
            setMedia([]) // Reset media
            fetchDescription()
        }
    }, [isOpen, listing])

    const fetchDescription = async () => {
        setIsLoading(true)
        try {
            const res = await fetch(`/api/listings/${listing.sku}/details`)
            const data = await res.json()
            if (data.error) throw new Error(data.error)
            setDescription(data.description || '(Description loading not supported in this version)')
            // TODO: In a real app, we would load existing media here
        } catch (e) {
            console.error(e)
            setDescription('(Failed to load description)')
        } finally {
            setIsLoading(false)
        }
    }



    const handleSave = async () => {
        setIsSaving(true)
        setError(null)
        try {
            // Run 2026 Security Sanitizer
            let finalDescription = description
            if (description && description !== '(Description loading not supported in this version)') {
                const { html, changes } = sanitizeDescription(description)
                finalDescription = html

                // Notify user if security fixes were applied
                if (changes.httpUpgraded > 0 || changes.scriptsRemoved > 0 || changes.unsafeAttributesRemoved > 0) {
                    toast.warning("Security Compliance Applied", {
                        description: `Fixed ${changes.httpUpgraded} insecure links and removed ${changes.scriptsRemoved + changes.unsafeAttributesRemoved} active content items.`
                    })
                }
            }

            await onSave(listing.sku, {
                title,
                price: parseFloat(price),
                quantity: parseInt(quantity),
                description: finalDescription !== '(Description loading not supported in this version)' ? finalDescription : undefined,
                media: media.map(m => m.file), // Pass raw files to parent handler
                offerId: listing.offerId
            })
            onClose()
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to save changes')
        } finally {
            setIsSaving(false)
        }
    }

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-2xl bg-white h-[80vh] flex flex-col p-0 gap-0">
                <DialogHeader className="p-6 pb-2">
                    <DialogTitle>Edit Listing: {listing.sku}</DialogTitle>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto px-6 py-2">
                    {error && (
                        <div className="bg-red-50 text-red-600 p-3 rounded-md flex items-center gap-2 text-sm mb-4">
                            <AlertCircle size={16} />
                            {error}
                        </div>
                    )}

                    <Tabs defaultValue="details" className="w-full">
                        <TabsList className="grid w-full grid-cols-3 mb-4">
                            <TabsTrigger value="details">Details</TabsTrigger>
                            <TabsTrigger value="media">Media (2026)</TabsTrigger>
                            <TabsTrigger value="description">Description</TabsTrigger>
                        </TabsList>

                        <TabsContent value="details" className="space-y-4 m-0">
                            <div className="grid gap-2">
                                <Label htmlFor="title">Title</Label>
                                <Input
                                    id="title"
                                    value={title}
                                    onChange={(e) => setTitle(e.target.value)}
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="grid gap-2">
                                    <Label htmlFor="price">Price ({listing.currency})</Label>
                                    <Input
                                        id="price"
                                        type="number"
                                        step="0.01"
                                        value={price}
                                        onChange={(e) => setPrice(e.target.value)}
                                    />
                                </div>
                                <div className="grid gap-2">
                                    <Label htmlFor="quantity">Quantity</Label>
                                    <Input
                                        id="quantity"
                                        type="number"
                                        value={quantity}
                                        onChange={(e) => setQuantity(e.target.value)}
                                    />
                                </div>
                            </div>
                        </TabsContent>

                        <TabsContent value="media" className="min-h-[300px] m-0">
                            <div className="bg-blue-50/50 p-4 rounded-lg mb-4 text-sm text-blue-700 border border-blue-100 flex items-start gap-2">
                                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                                <div>
                                    <p className="font-semibold">2026 Media Compliance</p>
                                    <p>eBay now prioritizes listings with video. Use this tab to add MP4/MOV videos (max 150MB) and high-res images.</p>
                                </div>
                            </div>
                            <MediaManager initialMedia={media} onMediaChange={setMedia} />
                        </TabsContent>

                        <TabsContent value="description" className="space-y-2 m-0 h-full">
                            <div className="grid gap-2 h-full">
                                <Label htmlFor="description">HTML Description</Label>
                                <Textarea
                                    id="description"
                                    className="min-h-[300px] font-mono text-xs leading-relaxed"
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    disabled={isLoading}
                                />
                                <p className="text-xs text-stone-400">
                                    {isLoading ? 'Fetching current description...' : 'Edit raw HTML description.'}
                                </p>
                            </div>
                        </TabsContent>
                    </Tabs>
                </div>

                <div className="flex justify-end gap-2 p-6 border-t bg-stone-50 rounded-b-lg">
                    <Button variant="outline" onClick={onClose} disabled={isSaving}>
                        Cancel
                    </Button>
                    <Button onClick={handleSave} disabled={isSaving} className="bg-blue-600 hover:bg-blue-700">
                        {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Save Changes
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    )
}
