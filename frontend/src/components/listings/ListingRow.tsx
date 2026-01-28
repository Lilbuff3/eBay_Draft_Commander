import { useState } from 'react'
import { Package, RefreshCw, Edit2, ExternalLink, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import type { Listing } from '@/components/ActiveListings'

interface ListingRowProps {
    listing: Listing
    isSelected: boolean
    isEditing: boolean
    filterStatus: 'active' | 'ended'
    isFetching: boolean
    onToggleSelect: (sku: string) => void
    onEditStart: (listing: Listing) => void
    onEditCancel: () => void
    onSave: (sku: string, qty: number, price: number) => Promise<void>
    onRefreshPrice: (sku: string) => void
    onRelist: (listing: Listing) => void
}

export function ListingRow({
    listing,
    isSelected,
    isEditing,
    filterStatus,
    isFetching,
    onToggleSelect,
    onEditStart,
    onEditCancel,
    onSave,
    onRefreshPrice,
    onRelist
}: ListingRowProps) {
    const [editQty, setEditQty] = useState(listing.availableQuantity.toString())
    const [editPrice, setEditPrice] = useState(listing.price.toString())
    const [isSaving, setIsSaving] = useState(false)

    // Sync local state when entering edit mode
    // Note: In a real app we might want a useEffect here, but parent controls the mode
    // We'll trust the parent passes correct initial values or we just init here.

    const handleSaveClick = async () => {
        const qty = parseInt(editQty)
        const price = parseFloat(editPrice)

        if (isNaN(qty) || qty < 0) return
        if (isNaN(price) || price < 0) return

        setIsSaving(true)
        await onSave(listing.sku, qty, price)
        setIsSaving(false)
    }

    // When edit starts, we need to ensure local state matches listing
    // Since we aren't using a useEffect to sync props to state (anti-pattern),
    // we rely on the fact that these inputs only mount when isEditing is true.
    // However, if we want to ensure latest values, we can double check.

    return (
        <div
            className={`px-6 py-3 transition-colors grid grid-cols-[auto_1fr_100px_80px_100px] gap-4 items-center ${isSelected || isEditing ? 'bg-blue-50/40' : 'hover:bg-stone-50'
                }`}
        >
            {/* Checkbox */}
            <input
                type="checkbox"
                checked={isSelected}
                onChange={() => onToggleSelect(listing.sku)}
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
            <div className="text-right flex items-center justify-end gap-2">
                {isEditing ? (
                    <Input
                        type="number"
                        value={editPrice}
                        onChange={(e) => setEditPrice(e.target.value)}
                        className="h-7 w-20 text-right text-xs ml-auto"
                        step="0.01"
                    />
                ) : (
                    <div className="flex items-center gap-2">
                        <div className={`font-medium ${listing.price === 0 ? 'text-red-500' : 'text-stone-700'}`}>
                            ${listing.price.toFixed(2)}
                        </div>
                        <button
                            onClick={() => onRefreshPrice(listing.sku)}
                            disabled={isFetching}
                            className="p-1 hover:bg-stone-100 rounded-full text-stone-400 hover:text-blue-500 transition-colors"
                            title="Refresh Price from eBay"
                        >
                            <RefreshCw size={12} className={isFetching ? 'animate-spin' : ''} />
                        </button>
                    </div>
                )}
            </div>

            {/* Qty */}
            <div className="flex justify-center">
                {isEditing ? (
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
                {isEditing ? (
                    <>
                        <Button
                            size="icon"
                            className="h-7 w-7 bg-green-500 hover:bg-green-600 text-white"
                            onClick={handleSaveClick}
                            disabled={isSaving}
                        >
                            <Check size={14} />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-stone-400 hover:text-red-500"
                            onClick={onEditCancel}
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
                                onClick={() => onRelist(listing)}
                                title="Relist"
                            >
                                <RefreshCw size={14} />
                            </Button>
                        ) : (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-stone-400 hover:text-blue-500"
                                onClick={() => {
                                    setEditQty(listing.availableQuantity.toString())
                                    setEditPrice(listing.price.toString())
                                    onEditStart(listing)
                                }}
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
    )
}
