import { useState } from 'react'
import { EditListingDialog } from './listings/EditListingDialog'
import { Button } from '@/components/ui/button'

export function TestMediaManager() {
    const [isOpen, setIsOpen] = useState(true)

    // Mock Listing
    const mockListing = {
        sku: 'TEST-VIDEO-2026',
        title: 'eBay 2026 Compliance Test Item',
        imageUrl: 'https://placehold.co/600x400',
        status: 'ACTIVE',
        price: 199.99,
        currency: 'USD',
        availableQuantity: 5,
        description: '<h1>Original Description</h1><p>Test</p>',
        categoryId: '1',
        condition: 'NEW'
    }

    return (
        <div className="p-10 flex flex-col items-center justify-center h-full bg-stone-100">
            <div className="text-center mb-8">
                <h1 className="text-2xl font-bold mb-2">Verification Harness</h1>
                <p className="text-stone-500">Testing MediaManager & Security Compliance</p>
            </div>

            <Button onClick={() => setIsOpen(true)} size="lg">
                Open Edit Dialog
            </Button>

            {isOpen && (
                <EditListingDialog
                    listing={mockListing as any}
                    isOpen={isOpen}
                    onClose={() => setIsOpen(false)}
                    onSave={async (sku, updates) => {
                        console.log('--- TEST SAVE ---')
                        console.log('SKU:', sku)
                        console.log('Updates:', updates)
                        alert('Save simulates success! Check console for data.')
                        setIsOpen(false)
                    }}
                />
            )}
        </div>
    )
}
