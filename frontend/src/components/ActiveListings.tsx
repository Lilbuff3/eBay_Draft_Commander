import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Package, RefreshCw, Edit2, ExternalLink, Check, X, AlertCircle, Power, Download } from 'lucide-react'
import { MigrationModal } from './MigrationModal'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
// Using native checkbox input
// Standard input type='checkbox' is safer if component is missing

interface Listing {
    sku: string
    offerId?: string
    listingId?: string
    title: string
    imageUrl: string | null
    status: string
    // Price & Qty
    price: number
    currency: string
    availableQuantity: number // API returns this now
    availability?: number // Legacy mapping
}

interface ListingsData {
    listings: Listing[]
    total: number
}

interface ActiveListingsProps {
    onClose?: () => void
}

export function ActiveListings({ onClose }: ActiveListingsProps) {
    const [data, setData] = useState<ListingsData | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState('')
    const [showMigration, setShowMigration] = useState(false)

    // Selection
    const [selectedSkus, setSelectedSkus] = useState<Set<string>>(new Set())

    // Edit State
    const [editingSku, setEditingSku] = useState<string | null>(null)
    const [editQty, setEditQty] = useState<string>('')
    const [editPrice, setEditPrice] = useState<string>('')
    const [isSaving, setIsSaving] = useState(false)

    // Bulk Action State
    const [isBulkActing, setIsBulkActing] = useState(false)

    const fetchListings = async () => {
        setIsLoading(true)
        setError(null)
        setSelectedSkus(new Set())
        try {
            const res = await fetch('/api/listings/active')
            const json = await res.json()
            if (json.error) throw new Error(json.error)

            // Map availability to availableQuantity if needed or normalize
            const normalized = {
                ...json,
                listings: json.listings.map((l: any) => ({
                    ...l,
                    availableQuantity: l.availableQuantity ?? l.availability ?? 0
                }))
            }
            setData(normalized)
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load listings')
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        fetchListings()
    }, [])

    const handleEditStart = (listing: Listing) => {
        setEditingSku(listing.sku)
        setEditQty(listing.availableQuantity.toString())
        setEditPrice(listing.price.toString())
    }

    const handleEditCancel = () => {
        setEditingSku(null)
        setEditQty('')
        setEditPrice('')
    }

    const handleSave = async (sku: string) => {
        const item = data?.listings.find(l => l.sku === sku)
        if (!item) return

        const newQty = parseInt(editQty)
        const newPrice = parseFloat(editPrice)

        if (isNaN(newQty) || newQty < 0) return
        if (isNaN(newPrice) || newPrice < 0) return

        setIsSaving(true)

        // Optimistic update
        const previousData = data
        if (data) {
            setData({
                ...data,
                listings: data.listings.map(l => l.sku === sku ? {
                    ...l,
                    availableQuantity: newQty,
                    price: newPrice
                } : l)
            })
        }

        try {
            // Use bulk endpoint for single update too, or the updated single endpoint
            const res = await fetch(`/api/listings/${sku}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    offerId: item.offerId,
                    quantity: newQty,
                    price: newPrice
                })
            })

            if (!res.ok) throw new Error('Update failed')

            setEditingSku(null)
        } catch (e) {
            console.error(e)
            // Revert on error
            setData(previousData)
            alert("Failed to update listing")
        } finally {
            setIsSaving(false)
        }
    }

    // Selection Logic
    const toggleSelect = (sku: string) => {
        const newSet = new Set(selectedSkus)
        if (newSet.has(sku)) newSet.delete(sku)
        else newSet.add(sku)
        setSelectedSkus(newSet)
    }

    const toggleSelectAll = () => {
        if (!filteredListings) return
        if (selectedSkus.size === filteredListings.length) {
            setSelectedSkus(new Set())
        } else {
            setSelectedSkus(new Set(filteredListings.map(l => l.sku)))
        }
    }

    // Bulk Actions
    // Tabs
    const [filterStatus, setFilterStatus] = useState<'active' | 'ended'>('active')

    // Bulk Actions
    const handleBulkPrice = async () => {
        const priceStr = prompt(`Enter new price for ${selectedSkus.size} items:`)
        if (!priceStr) return
        const newPrice = parseFloat(priceStr)
        if (isNaN(newPrice) || newPrice < 0) return alert("Invalid price")

        setIsBulkActing(true)
        try {
            const updates = []
            for (const sku of selectedSkus) {
                const item = data?.listings.find(l => l.sku === sku)
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
                fetchListings()
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
                const item = data?.listings.find(l => l.sku === sku)
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
                fetchListings()
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
                const item = data?.listings.find(l => l.sku === sku)
                if (item?.offerId) {
                    await fetch(`/api/listings/${item.offerId}/withdraw`, { method: 'POST' })
                }
            }
            fetchListings()
        } catch (e) {
            alert('Some items failed to end')
        } finally {
            setIsBulkActing(false)
        }
    }

    const handleRelist = async (listing: Listing) => {
        if (!confirm(`Relist ${listing.title}?`)) return
        try {
            const res = await fetch(`/api/listings/${listing.offerId}/publish`, { method: 'POST' })
            if (res.ok) {
                fetchListings()
            } else {
                const err = await res.json()
                alert(`Failed: ${err.error}`)
            }
        } catch (e) {
            alert('Relist failed')
        }
    }

    const filteredListings = data?.listings.filter(listing => {
        const matchesSearch = listing.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            listing.sku.toLowerCase().includes(searchQuery.toLowerCase())

        const isActive = listing.status === 'PUBLISHED'
        const matchesTab = filterStatus === 'active' ? isActive : !isActive

        return matchesSearch && matchesTab
    }) || []

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="bg-white rounded-3xl border border-stone-200 shadow-xl overflow-hidden flex flex-col h-[75vh] w-full max-w-5xl mx-auto"
        >
            {/* Header */}
            <div className="px-6 py-4 border-b border-stone-100 bg-gradient-to-r from-blue-50 to-white flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-500 flex items-center justify-center text-white shadow-sm">
                        <Package size={20} />
                    </div>
                    <div>
                        <h2 className="font-semibold text-stone-800">Inventory Manager</h2>
                        <div className="flex items-center gap-2 mt-1">
                            <div className="flex bg-stone-100 rounded-lg p-0.5">
                                <button
                                    className={`px-3 py-0.5 text-xs font-medium rounded-md transition-all ${filterStatus === 'active' ? 'bg-white shadow text-blue-600' : 'text-stone-500 hover:text-stone-700'}`}
                                    onClick={() => setFilterStatus('active')}
                                >
                                    Active
                                </button>
                                <button
                                    className={`px-3 py-0.5 text-xs font-medium rounded-md transition-all ${filterStatus === 'ended' ? 'bg-white shadow text-blue-600' : 'text-stone-500 hover:text-stone-700'}`}
                                    onClick={() => setFilterStatus('ended')}
                                >
                                    Ended
                                </button>
                            </div>
                            <span className="text-xs text-stone-400 ml-2">
                                {data?.total || 0} total
                            </span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => setShowMigration(true)} className="gap-2 text-blue-600 bg-blue-50 border-blue-100 hover:bg-blue-100">
                        <Download size={16} />
                        Import
                    </Button>
                    <Button variant="ghost" size="icon" onClick={fetchListings} disabled={isLoading}>
                        <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
                    </Button>
                    {onClose && (
                        <Button variant="ghost" size="sm" onClick={onClose}>
                            Close
                        </Button>
                    )}
                </div>
            </div>

            {/* Bulk Action Bar */}
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

            {/* Search & Filter */}
            <div className="px-6 py-3 border-b border-stone-100 shrink-0 bg-stone-50 flex items-center gap-4">
                <input
                    type="checkbox"
                    checked={filteredListings.length > 0 && selectedSkus.size === filteredListings.length}
                    onChange={toggleSelectAll}
                    className="w-4 h-4 rounded border-stone-300 text-blue-600 focus:ring-blue-500"
                />
                <Input
                    placeholder="Search by Title or SKU..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-white"
                />
            </div>

            {/* Listings Header */}
            <div className="px-6 py-2 border-b border-stone-100 bg-stone-50 grid grid-cols-[auto_1fr_100px_80px_100px] gap-4 text-xs font-semibold text-stone-500">
                <div className="w-4"></div> {/* Checkbox spacer */}
                <div>ITEM</div>
                <div className="text-right">PRICE</div>
                <div className="text-center">QTY</div>
                <div className="text-right">ACTIONS</div>
            </div>

            {/* Listings Grid */}
            <div className="flex-1 overflow-hidden relative">
                <ScrollArea className="h-full">
                    {isLoading ? (
                        <div className="flex items-center justify-center h-64 text-stone-400">
                            <RefreshCw size={24} className="animate-spin mr-2" />
                            Loading inventory...
                        </div>
                    ) : error ? (
                        <div className="flex items-center justify-center h-64 text-red-500 p-4 gap-2">
                            <AlertCircle size={20} />
                            {error}
                        </div>
                    ) : filteredListings.length === 0 ? (
                        <div className="flex items-center justify-center h-64 text-stone-400">
                            {searchQuery ? 'No matching listings' : 'No active listings found'}
                        </div>
                    ) : (
                        <div className="divide-y divide-stone-100">
                            {filteredListings.map(listing => (
                                <div
                                    key={listing.sku}
                                    className={`px-6 py-3 transition-colors grid grid-cols-[auto_1fr_100px_80px_100px] gap-4 items-center ${selectedSkus.has(listing.sku) || editingSku === listing.sku ? 'bg-blue-50/40' : 'hover:bg-stone-50'
                                        }`}
                                >
                                    {/* Checkbox */}
                                    <input
                                        type="checkbox"
                                        checked={selectedSkus.has(listing.sku)}
                                        onChange={() => toggleSelect(listing.sku)}
                                        className="w-4 h-4 rounded border-stone-300 text-blue-600 focus:ring-blue-500"
                                    />

                                    {/* Item Info */}
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div className="w-10 h-10 rounded bg-stone-100 overflow-hidden flex-shrink-0 border border-stone-200">
                                            {listing.imageUrl ? (
                                                <img src={listing.imageUrl} alt="" className="w-full h-full object-cover" />
                                            ) : (
                                                <div className="w-full h-full flex items-center justify-center text-stone-300">
                                                    <Package size={16} />
                                                </div>
                                            )}
                                        </div>
                                        <div className="min-w-0">
                                            <div className="text-sm font-medium text-stone-800 truncate" title={listing.title}>
                                                {listing.title}
                                            </div>
                                            <div className="text-[10px] text-stone-400 font-mono">
                                                {listing.sku}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Price */}
                                    <div className="text-right">
                                        {editingSku === listing.sku ? (
                                            <Input
                                                type="number"
                                                value={editPrice}
                                                onChange={(e) => setEditPrice(e.target.value)}
                                                className="h-7 w-20 text-right text-xs ml-auto"
                                                step="0.01"
                                            />
                                        ) : (
                                            <div className="font-medium text-stone-700">
                                                ${listing.price.toFixed(2)}
                                            </div>
                                        )}
                                    </div>

                                    {/* Qty */}
                                    <div className="flex justify-center">
                                        {editingSku === listing.sku ? (
                                            <Input
                                                type="number"
                                                value={editQty}
                                                onChange={(e) => setEditQty(e.target.value)}
                                                className="h-7 w-16 text-center text-xs"
                                            />
                                        ) : (
                                            <Badge
                                                variant="secondary"
                                                className={`text-[10px] h-5 px-2 ${listing.availableQuantity > 0
                                                    ? 'bg-green-50 text-green-700'
                                                    : 'bg-red-50 text-red-700'
                                                    }`}
                                            >
                                                {listing.availableQuantity}
                                            </Badge>
                                        )}
                                    </div>

                                    {/* Actions */}
                                    <div className="flex items-center justify-end gap-1">
                                        {editingSku === listing.sku ? (
                                            <>
                                                <Button
                                                    size="icon"
                                                    className="h-7 w-7 bg-green-500 hover:bg-green-600 text-white"
                                                    onClick={() => handleSave(listing.sku)}
                                                    disabled={isSaving}
                                                >
                                                    <Check size={14} />
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-7 w-7 text-stone-400 hover:text-red-500"
                                                    onClick={handleEditCancel}
                                                    disabled={isSaving}
                                                >
                                                    <X size={14} />
                                                </Button>
                                            </>
                                        ) : (
                                            <>
                                                {filterStatus === 'ended' ? (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-7 w-7 text-blue-500 hover:text-blue-700"
                                                        onClick={() => handleRelist(listing)}
                                                        title="Relist"
                                                    >
                                                        <RefreshCw size={14} />
                                                    </Button>
                                                ) : (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-7 w-7 text-stone-400 hover:text-blue-500"
                                                        onClick={() => handleEditStart(listing)}
                                                    >
                                                        <Edit2 size={14} />
                                                    </Button>
                                                )}

                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-7 w-7 text-stone-400 hover:text-stone-600"
                                                    onClick={() => window.open(`https://www.ebay.com/itm/${listing.listingId}`, '_blank')}
                                                    title="View on eBay"
                                                >
                                                    <ExternalLink size={14} />
                                                </Button>
                                            </>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </ScrollArea>
            </div>

            {/* Footer */}
            <div className="px-6 py-3 bg-stone-50 border-t border-stone-100 flex items-center justify-between text-xs text-stone-400 shrink-0">
                <span>
                    {selectedSkus.size > 0 ? `${selectedSkus.size} selected` : `Showing ${filteredListings.length} items`}
                </span>
                <span>eBay Inventory Sync</span>
            </div>


            <AnimatePresence>
                {showMigration && (
                    <MigrationModal
                        onClose={() => setShowMigration(false)}
                        onSuccess={() => {
                            fetchListings()
                            // Keep modal open to show status? Or close?
                            // Let's keep it open so they see the success message in the modal
                        }}
                    />
                )}
            </AnimatePresence>
        </motion.div >
    )
}
