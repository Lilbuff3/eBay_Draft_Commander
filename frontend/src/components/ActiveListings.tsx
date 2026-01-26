import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Package, RefreshCw, AlertCircle, Download } from 'lucide-react'
import { MigrationModal } from './MigrationModal'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
import { BulkActionBar } from './listings/BulkActionBar'
import { ListingRow } from './listings/ListingRow'

export interface Listing {
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
    const [fetchingSkus, setFetchingSkus] = useState<Set<string>>(new Set())

    // Edit State
    const [editingSku, setEditingSku] = useState<string | null>(null)

    // Bulk Action State
    const [isBulkActing, setIsBulkActing] = useState(false)

    // Tabs
    const [filterStatus, setFilterStatus] = useState<'active' | 'ended'>('active')

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

    const handleSave = async (sku: string, newQty: number, newPrice: number) => {
        const item = data?.listings.find(l => l.sku === sku)
        if (!item) return

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
        }
    }

    const refreshPrice = async (sku: string) => {
        setFetchingSkus(prev => new Set(prev).add(sku))
        try {
            const res = await fetch(`/api/listings/${sku}/details`)
            if (!res.ok) throw new Error('Failed to fetch price')

            const details = await res.json()

            if (data) {
                setData({
                    ...data,
                    listings: data.listings.map(l => l.sku === sku ? {
                        ...l,
                        price: details.price,
                        availableQuantity: details.quantity,
                        offerId: details.offerId
                    } : l)
                })
            }
        } catch (e) {
            console.error(e)
            alert('Could not fetch latest price')
        } finally {
            setFetchingSkus(prev => {
                const next = new Set(prev)
                next.delete(sku)
                return next
            })
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
            <BulkActionBar
                selectedSkus={selectedSkus}
                listings={data?.listings}
                isBulkActing={isBulkActing}
                filterStatus={filterStatus}
                onRefresh={fetchListings}
                setIsBulkActing={setIsBulkActing}
                onClearSelection={() => setSelectedSkus(new Set())}
            />

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
                                <ListingRow
                                    key={listing.sku}
                                    listing={listing}
                                    isSelected={selectedSkus.has(listing.sku)}
                                    isEditing={editingSku === listing.sku}
                                    filterStatus={filterStatus}
                                    isFetching={fetchingSkus.has(listing.sku)}
                                    onToggleSelect={toggleSelect}
                                    onEditStart={(l) => setEditingSku(l.sku)}
                                    onEditCancel={() => setEditingSku(null)}
                                    onSave={handleSave}
                                    onRefreshPrice={refreshPrice}
                                    onRelist={handleRelist}
                                />
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
                        }}
                    />
                )}
            </AnimatePresence>
        </motion.div >
    )
}
