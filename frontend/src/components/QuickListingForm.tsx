import { useState } from 'react'
import { PhotoUpload } from '@/components/PhotoUpload'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Loader2, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

export function QuickListingForm() {
    const [photos, setPhotos] = useState<File[]>([])
    const [isCreating, setIsCreating] = useState(false)
    const [itemName, setItemName] = useState('')
    const [price, setPrice] = useState('')
    const [description, setDescription] = useState('')

    const handleCreateListing = async () => {
        if (photos.length === 0) {
            toast.error('Please add at least one photo')
            return
        }

        setIsCreating(true)

        try {
            // Create FormData for file upload
            const formData = new FormData()

            photos.forEach((photo, index) => {
                formData.append(`photo${index}`, photo)
            })

            formData.append('itemName', itemName)
            formData.append('price', price)
            formData.append('description', description)

            // Upload to server
            const response = await fetch('/api/listing/create-from-photos', {
                method: 'POST',
                body: formData,
            })

            if (!response.ok) {
                throw new Error('Failed to create listing')
            }

            const result = await response.json()

            toast.success('Listing created successfully!', {
                description: `eBay ID: ${result.listingId || result.offerId}`,
            })

            // Reset form
            setPhotos([])
            setItemName('')
            setPrice('')
            setDescription('')

        } catch (error) {
            console.error('Error creating listing:', error)
            toast.error('Failed to create listing', {
                description: error instanceof Error ? error.message : 'Unknown error',
            })
        } finally {
            setIsCreating(false)
        }
    }

    return (
        <div className="h-full overflow-y-auto mobile-scroll">
            <div className="max-w-2xl mx-auto p-4 space-y-6 pb-20">
                <div>
                    <h1 className="text-2xl font-bold mb-2">Create Listing</h1>
                    <p className="text-slate-600 dark:text-slate-400">
                        Upload photos from your gallery or camera
                    </p>
                </div>

                <PhotoUpload
                    onPhotosSelected={setPhotos}
                    maxPhotos={12}
                />

                <Card className="p-6 space-y-4">
                    <div>
                        <label htmlFor="itemName" className="text-sm font-medium mb-2 block">Item Name (Optional)</label>
                        <Input
                            id="itemName"
                            placeholder="Leave blank for AI to suggest"
                            value={itemName}
                            onChange={(e) => setItemName(e.target.value)}
                            className="tap-target"
                        />
                    </div>

                    <div>
                        <label htmlFor="price" className="text-sm font-medium mb-2 block">Price (Optional)</label>
                        <Input
                            id="price"
                            type="number"
                            placeholder="Leave blank for AI to estimate"
                            value={price}
                            onChange={(e) => setPrice(e.target.value)}
                            className="tap-target"
                        />
                    </div>

                    <div>
                        <label htmlFor="description" className="text-sm font-medium mb-2 block">Description (Optional)</label>
                        <textarea
                            id="description"
                            placeholder="Add any specific details..."
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            rows={3}
                            className="tap-target resize-none w-full rounded-md border border-slate-300 px-3 py-2"
                        />
                    </div>

                    <Button
                        onClick={handleCreateListing}
                        disabled={photos.length === 0 || isCreating}
                        className="w-full tap-target min-h-[48px]"
                        size="lg"
                    >
                        {isCreating ? (
                            <>
                                <Loader2 className="mr-2 animate-spin" size={20} />
                                Creating Listing...
                            </>
                        ) : (
                            <>
                                <Sparkles className="mr-2" size={20} />
                                Create Listing with AI
                            </>
                        )}
                    </Button>

                    {photos.length > 0 && (
                        <p className="text-xs text-center text-slate-500">
                            AI will analyze your {photos.length} photo{photos.length > 1 ? 's' : ''} and generate title, description, category, and pricing
                        </p>
                    )}
                </Card>
            </div>
        </div>
    )
}
