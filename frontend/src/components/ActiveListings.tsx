import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Package, RefreshCw, AlertCircle, Download, ShoppingBag } from 'lucide-react'
import { toast } from 'sonner'
import { apiFetch, fetchRecentOrders, type Order } from '@/lib/api'
import { MigrationModal } from './MigrationModal'
import { EditListingDialog } from './listings/EditListingDialog'
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
    description?: string
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
    const [editingListing, setEditingListing] = useState<Listing | null>(null)

    // Bulk Action State
    const [isBulkActing, setIsBulkActing] = useState(false)

    // Tabs
    const [filterStatus, setFilterStatus] = useState<'active' | 'ended' | 'sold'>('active')

    // Sold orders
    const [orders, setOrders] = useState<Order[]>([])
    const [ordersLoading, setOrdersLoading] = useState(false)
    const [ordersError, setOrdersError] = useState<string | null>(null)

    const fetchOrders = async () => {
        setOrdersLoading(true)
        setOrdersError(null)
        try {
            const res = await fetchRecentOrders('90', 100)
            setOrders(res.orders)
        } catch (e) {
            setOrdersError(e instanceof Error ? e.message : 'Failed to load orders')
        } finally {
            setOrdersLoading(false)
        }
    }

    useEffect(() => {
        if (filterStatus === 'sold' && orders.length === 0 && !ordersLoading) {
            fetchOrders()
        }
    }, [filterStatus]) // eslint-disable-line react-hooks/exhaustive-deps

    const fetchListings = async () => {
        setIsLoading(true)
        setError(null)
        setSelectedSkus(new Set())
        try {
            const json = await apiFetch<{ listings: (Listing & { availability?: number })[]; total: number; error?: string }>('/api/listings/active')
            if (json.error) throw new Error(json.error)

            // Map availability to availableQuantity if needed or normalize
            const normalized = {
                ...json,
                listings: json.listings.map((l) => ({
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

    const handleSave = async (sku: string, updates: Partial<Listing> & { quantity?: number }) => {
        // Optimistic update
        const previousData = data
        if (data) {
            setData({
                ...data,
                listings: data.listings.map(l => l.sku === sku ? {
                    ...l,
                    title: updates.title || l.title,
                    availableQuantity: updates.quantity || l.availableQuantity,
                    price: updates.price || l.price
                } : l)
            })
        }

        try {
            await apiFetch(`/api/listings/${sku}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            })

            setEditingListing(null)
        } catch (e) {
            console.error(e)
            // Revert on error
            setData(previousData)
            toast.error(`Failed to update listing: ${e instanceof Error ? e.message : 'Unknown error'}`)
            throw e // Rethrow so dialog knows it failed
        }
    }

    const refreshPrice = async (sku: string) => {
        setFetchingSkus(prev => new Set(prev).add(sku))
        try {
            const details = await apiFetch<{ price: number; quantity: number; offerId: string }>(`/api/listings/${sku}/details`)

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
            toast.error('Could not fetch latest price')
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
            await apiFetch(`/api/listings/${listing.offerId}/publish`, { method: 'POST' })
            fetchListings()
        } catch (e) {
            toast.error(`Relist failed: ${e instanceof Error ? e.message : 'Unknown error'}`)
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
            className="bg-white flex flex-col h-full w-full overflow-hidden"
        >
            {/* Header */}
            <div className="px-6 py-4 border-b border-stone-100 bg-persimmon-50/40 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-persimmon-500 flex items-center justify-center text-white shadow-sm">
                        <Package size={20} />
                    </div>
                    <div>
                        <h2 className="font-display font-bold text-ink-800 text-lg tracking-tight">Inventory Manager</h2>
                        <div className="flex items-center gap-2 mt-1">
                            <div className="flex bg-stone-100 rounded-lg p-0.5">
                                {(['active', 'ended', 'sold'] as const).map(tab => (
                                    <button
                                        key={tab}
                                        className={`px-3 py-0.5 text-xs font-medium rounded-md transition capitalize ${filterStatus === tab ? 'bg-white shadow text-persimmon-600' : 'text-stone-500 hover:text-stone-700'}`}
                                        onClick={() => setFilterStatus(tab)}
                                    >
                                        {tab}
                                    </button>
                                ))}
                            </div>
                            <span className="text-xs text-stone-400 ml-2">
                                {data?.total || 0} total
                            </span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => setShowMigration(true)} className="gap-2 text-persimmon-600 bg-persimmon-50 border-persimmon-100 hover:bg-persimmon-100">
                        <Download size={16} />
                        Import
                    </Button>
                    <Button variant="ghost" size="icon" onClick={fetchListings} disabled={isLoading} aria-label="Refresh active listings" title="Refresh">
                        <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
                    </Button>
                    {onClose && (
                        <Button variant="ghost" size="sm" onClick={onClose}>
                            Close
                        </Button>
                    )}
                </div>
            </div>

            {/* Bulk Action Bar — only for active/ended */}
            {filterStatus !== 'sold' && (
                <BulkActionBar
                    selectedSkus={selectedSkus}
                    listings={data?.listings}
                    isBulkActing={isBulkActing}
                    filterStatus={filterStatus}
                    onRefresh={fetchListings}
                    setIsBulkActing={setIsBulkActing}
                    onClearSelection={() => setSelectedSkus(new Set())}
                />
            )}

            {/* Search & Filter */}
            <div className="px-6 py-3 border-b border-stone-100 shrink-0 bg-stone-50 flex items-center gap-4">
                {filterStatus !== 'sold' && (
                    <input
                        type="checkbox"
                        checked={filteredListings.length > 0 && selectedSkus.size === filteredListings.length}
                        onChange={toggleSelectAll}
                        className="w-4 h-4 rounded border-stone-300 text-persimmon-600 focus:ring-persimmon-500"
                    />
                )}
                <Input
                    placeholder={filterStatus === 'sold' ? 'Search orders…' : 'Search by Title or SKU…'}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-white"
                />
            </div>

            {filterStatus === 'sold' ? (
                <>
                    {/* Orders Header */}
                    <div className="px-6 py-2 border-b border-stone-100 bg-stone-50 grid grid-cols-[1fr_100px_80px_120px] gap-4 text-xs font-semibold text-stone-500">
                        <div>ORDER</div>
                        <div className="text-right">TOTAL</div>
                        <div className="text-center">ITEMS</div>
                        <div className="text-right">DATE</div>
                    </div>

                    {/* Orders Grid */}
                    <div className="flex-1 overflow-hidden relative">
                        <ScrollArea className="h-full">
                            {ordersLoading ? (
                                <div className="flex items-center justify-center h-64 text-stone-400">
                                    <RefreshCw size={24} className="animate-spin mr-2" />
                                    Loading orders…
                                </div>
                            ) : ordersError ? (
                                <div className="flex items-center justify-center h-64 text-red-500 p-4 gap-2">
                                    <AlertCircle size={20} />
                                    {ordersError}
                                </div>
                            ) : orders.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-64 text-stone-400 gap-2">
                                    <ShoppingBag size={32} className="text-stone-200" />
                                    No orders in the last 90 days
                                </div>
                            ) : (
                                <div className="divide-y divide-stone-100">
                                    {orders
                                        .filter(o => !searchQuery || o.orderId.toLowerCase().includes(searchQuery.toLowerCase()) || o.buyer.toLowerCase().includes(searchQuery.toLowerCase()))
                                        .map(order => (
                                            <div key={order.orderId} className="px-6 py-3 grid grid-cols-[1fr_100px_80px_120px] gap-4 items-center hover:bg-stone-50 transition-colors">
                                                <div>
                                                    <p className="text-sm font-medium text-ink-800 truncate">{order.orderId}</p>
                                                    <p className="text-[11px] text-stone-400 mt-0.5">{order.buyer}</p>
                                                </div>
                                                <div className="text-right font-semibold text-sage-700">${order.total.toFixed(2)}</div>
                                                <div className="text-center">
                                                    <span className="text-xs bg-stone-100 text-stone-600 px-2 py-0.5 rounded-full">{order.itemCount}</span>
                                                </div>
                                                <div className="text-right text-xs text-stone-400">
                                                    {new Date(order.creationDate).toLocaleDateString()}
                                                </div>
                                            </div>
                                        ))
                                    }
                                </div>
                            )}
                        </ScrollArea>
                    </div>

                    {/* Footer */}
                    <div className="px-6 py-3 bg-stone-50 border-t border-stone-100 flex items-center justify-between text-xs text-stone-400 shrink-0">
                        <span>Showing {orders.length} orders · last 90 days</span>
                        <button onClick={fetchOrders} className="hover:text-persimmon-600 transition-colors flex items-center gap-1">
                            <RefreshCw size={11} className={ordersLoading ? 'animate-spin' : ''} />
                            Refresh
                        </button>
                    </div>
                </>
            ) : (
                <>
                    {/* Listings Header */}
                    <div className="px-6 py-2 border-b border-stone-100 bg-stone-50 grid grid-cols-[auto_1fr_100px_80px_100px] gap-4 text-xs font-semibold text-stone-500">
                        <div className="w-4"></div>
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
                                    Loading inventory…
                                </div>
                            ) : error ? (
                                <div className="flex items-center justify-center h-64 text-red-500 p-4 gap-2">
                                    <AlertCircle size={20} />
                                    {error}
                                </div>
                            ) : filteredListings.length === 0 ? (
                                <div className="flex items-center justify-center h-64 text-stone-400">
                                    {searchQuery ? 'No matching listings' : filterStatus === 'active' ? 'No active listings' : 'No ended listings'}
                                </div>
                            ) : (
                                <div className="divide-y divide-stone-100">
                                    {filteredListings.map(listing => (
                                        <ListingRow
                                            key={listing.sku}
                                            listing={listing}
                                            isSelected={selectedSkus.has(listing.sku)}
                                            isEditing={false}
                                            filterStatus={filterStatus}
                                            isFetching={fetchingSkus.has(listing.sku)}
                                            onToggleSelect={toggleSelect}
                                            onEditStart={(l) => setEditingListing(l)}
                                            onEditCancel={() => setEditingListing(null)}
                                            onSave={(sku, qty, price) => handleSave(sku, { quantity: qty, price })}
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
                </>
            )}


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

            {/* Edit DIALOG */}
            {editingListing && (
                <EditListingDialog
                    listing={editingListing}
                    isOpen={!!editingListing}
                    onClose={() => setEditingListing(null)}
                    onSave={handleSave}
                />
            )}
        </motion.div >
    )
}
