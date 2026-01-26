import { motion, AnimatePresence } from 'framer-motion'
import { Edit2, Power } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { Listing } from '@/components/ActiveListings'

interface BulkActionBarProps {
    selectedSkus: Set<string>
    listings: Listing[] | undefined
    isBulkActing: boolean
    filterStatus: 'active' | 'ended'
    onRefresh: () => void
    setIsBulkActing: (val: boolean) => void
    onClearSelection: () => void
}

export function BulkActionBar({
    selectedSkus,
    listings,
    isBulkActing,
    filterStatus,
    onRefresh,
    setIsBulkActing,
}: BulkActionBarProps) {

    const handleBulkPrice = async () => {
        const priceStr = prompt(`Enter new price for ${selectedSkus.size} items:`)
        if (!priceStr) return
        const newPrice = parseFloat(priceStr)
        if (isNaN(newPrice) || newPrice < 0) return alert("Invalid price")

        setIsBulkActing(true)
        try {
            const updates = []
            for (const sku of selectedSkus) {
                const item = listings?.find(l => l.sku === sku)
                if (item?.offerId) {
                    updates.push({
                        sku: sku,
                        offerId: item.offerId,
                        price: newPrice
                    })
                }
            }
            if (updates.length > 0) {
                await fetch('/api/listings/bulk', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ updates })
                })
                onRefresh()
            }
        } catch (e) {
            alert('Bulk update failed')
        } finally {
            setIsBulkActing(false)
        }
    }

    const handleBulkTitle = async () => {
        const mode = prompt("Title Edit Mode:\n1 = Find & Replace\n2 = Append\n3 = Prepend\n\nEnter 1, 2, or 3:")
        if (!mode || !['1', '2', '3'].includes(mode)) return

        let findText = '', replaceText = '', appendText = '', prependText = ''

        if (mode === '1') {
            findText = prompt("Enter text to FIND:") || ''
            replaceText = prompt("Enter REPLACEMENT text:") || ''
            if (!findText) return alert("Find text is required")
        } else if (mode === '2') {
            appendText = prompt("Text to APPEND to end of title:") || ''
            if (!appendText) return alert("Append text is required")
        } else if (mode === '3') {
            prependText = prompt("Text to PREPEND to start of title:") || ''
            if (!prependText) return alert("Prepend text is required")
        }

        setIsBulkActing(true)
        try {
            const updates = []
            for (const sku of selectedSkus) {
                const item = listings?.find(l => l.sku === sku)
                if (item?.offerId) {
                    let newTitle = item.title
                    if (mode === '1') {
                        newTitle = item.title.replace(new RegExp(findText, 'gi'), replaceText)
                    } else if (mode === '2') {
                        newTitle = item.title + appendText
                    } else if (mode === '3') {
                        newTitle = prependText + item.title
                    }
                    // eBay title max is 80 chars
                    newTitle = newTitle.substring(0, 80)
                    updates.push({ offerId: item.offerId, title: newTitle })
                }
            }
            if (updates.length > 0) {
                const res = await fetch('/api/listings/bulk/title', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ updates })
                })
                const result = await res.json()
                if (result.failed > 0) {
                    alert(`Updated ${result.updated}, Failed ${result.failed}`)
                }
                onRefresh()
            }
        } catch (e) {
            alert('Bulk title update failed')
        } finally {
            setIsBulkActing(false)
        }
    }

    const handleBulkEnd = async () => {
        if (!confirm(`End ${selectedSkus.size} listings? This is permanent.`)) return
        setIsBulkActing(true)

        try {
            for (const sku of selectedSkus) {
                const item = listings?.find(l => l.sku === sku)
                if (item?.offerId) {
                    await fetch(`/api/listings/${item.offerId}/withdraw`, { method: 'POST' })
                }
            }
            onRefresh()
        } catch (e) {
            alert('Some items failed to end')
        } finally {
            setIsBulkActing(false)
        }
    }

    return (
        <AnimatePresence>
            {selectedSkus.size > 0 && (
                <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="bg-blue-600 text-white px-6 py-2 flex items-center justify-between shrink-0"
                >
                    <div className="text-sm font-medium">
                        {selectedSkus.size} selected
                    </div>
                    <div className="flex items-center gap-2">
                        {filterStatus === 'active' && (
                            <Button
                                size="sm"
                                variant="secondary"
                                className="h-8 bg-blue-500 text-white border-blue-400 hover:bg-blue-400"
                                onClick={handleBulkEnd}
                                disabled={isBulkActing}
                            >
                                <Power size={14} className="mr-2" />
                                End Listings
                            </Button>
                        )}
                        <Button
                            size="sm"
                            variant="secondary"
                            className="h-8 bg-white text-blue-700 hover:bg-stone-100"
                            onClick={handleBulkPrice}
                            disabled={isBulkActing}
                        >
                            <Edit2 size={14} className="mr-2" />
                            Bulk Price
                        </Button>
                        <Button
                            size="sm"
                            variant="secondary"
                            className="h-8 bg-white text-blue-700 hover:bg-stone-100"
                            onClick={handleBulkTitle}
                            disabled={isBulkActing}
                        >
                            <Edit2 size={14} className="mr-2" />
                            Bulk Title
                        </Button>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    )
}
