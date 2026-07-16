import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Package, RefreshCw, AlertCircle, Download, ShoppingBag, CheckSquare, Square, ListChecks, TrendingDown, XCircle } from 'lucide-react'
import { toast } from 'sonner'
import { apiFetch, fetchRecentOrders, type Order } from '@/lib/api'
import { cn } from '@/lib/utils'
import { MigrationModal } from './MigrationModal'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
import { InventoryCard } from './listings/InventoryCard'
import {
    Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { ageDays, staleTag, TAG_META, DEAD_AGE, type StaleTag } from '@/lib/staleness'

export interface Listing {
    sku: string
    offerId?: string
    listingId?: string
    title: string
    imageUrl: string | null
    status: string
    price: number
    currency: string
    availableQuantity: number
    availability?: number
    description?: string
    watchCount?: number
    startTime?: string | null
}

interface ListingsData {
    listings: Listing[]
    total: number
}

interface ActiveListingsProps {
    onClose?: () => void
}

type ActionBusy = { price?: boolean; promote?: boolean; end?: boolean }

export function ActiveListings({ onClose }: ActiveListingsProps) {
    const [data, setData] = useState<ListingsData | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState('')
    const [showMigration, setShowMigration] = useState(false)

    const [filterStatus, setFilterStatus] = useState<'active' | 'sold'>('active')
    const [staleFilter, setStaleFilter] = useState<'all' | StaleTag>('all')
    const [busyById, setBusyById] = useState<Record<string, ActionBusy>>({})

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
        try {
            const json = await apiFetch<{ listings: (Listing & { availability?: number })[]; total: number; error?: string }>('/api/listings/active')
            if (json.error) throw new Error(json.error)
            const normalized: ListingsData = {
                total: json.total,
                listings: json.listings.map((l) => ({
                    ...l,
                    availableQuantity: l.availableQuantity ?? l.availability ?? 0,
                })),
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

    const setBusy = (id: string, kind: keyof ActionBusy, val: boolean) =>
        setBusyById(prev => ({ ...prev, [id]: { ...prev[id], [kind]: val } }))

    const errMsg = (e: unknown) => (e instanceof Error ? e.message : 'Unknown error')

    const dropPrice = async (listing: Listing, newPrice: number) => {
        const id = listing.listingId
        if (!id) return
        setBusy(id, 'price', true)
        const previous = data
        if (data) {
            setData({ ...data, listings: data.listings.map(l => l.listingId === id ? { ...l, price: newPrice } : l) })
        }
        try {
            await apiFetch(`/api/listings/${id}/price`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ price: newPrice }),
            })
            toast.success(`Price dropped to $${newPrice.toFixed(2)}`)
        } catch (e) {
            setData(previous)
            toast.error(`Drop failed: ${errMsg(e)}`)
        } finally {
            setBusy(id, 'price', false)
        }
    }

    // One shared confirm dialog for promote / end / bulk — replaces window.confirm
    // (unstyled OS dialog, jarring inside a PWA).
    const [confirmAction, setConfirmAction] = useState<{
        title: string
        description: string
        confirmLabel: string
        destructive: boolean
        onConfirm: () => void
    } | null>(null)

    const promote = (listing: Listing) => {
        if (!listing.listingId) return
        setConfirmAction({
            title: 'Promote this listing?',
            description: `"${listing.title}" — you only pay the ad rate when it sells.`,
            confirmLabel: 'Promote',
            destructive: false,
            onConfirm: () => void doPromote(listing),
        })
    }

    const doPromote = async (listing: Listing) => {
        const id = listing.listingId
        if (!id) return
        setBusy(id, 'promote', true)
        try {
            await apiFetch(`/api/listings/${id}/promote`, { method: 'POST' })
            toast.success('Listing promoted')
        } catch (e) {
            toast.error(`Promote failed: ${errMsg(e)}`)
        } finally {
            setBusy(id, 'promote', false)
        }
    }

    const endListing = (listing: Listing) => {
        if (!listing.listingId) return
        setConfirmAction({
            title: 'End this listing?',
            description: `"${listing.title}" will be removed from eBay. This can't be undone.`,
            confirmLabel: 'End listing',
            destructive: true,
            onConfirm: () => void doEndListing(listing),
        })
    }

    const doEndListing = async (listing: Listing) => {
        const id = listing.listingId
        if (!id) return
        setBusy(id, 'end', true)
        try {
            await apiFetch(`/api/listings/${id}/end`, { method: 'POST' })
            setData(d => d ? { ...d, listings: d.listings.filter(l => l.listingId !== id) } : d)
            toast.success('Listing ended')
        } catch (e) {
            toast.error(`End failed: ${errMsg(e)}`)
        } finally {
            setBusy(id, 'end', false)
        }
    }

    // --- Bulk actions (select mode) ---
    const [selectMode, setSelectMode] = useState(false)
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
    const [bulkRunning, setBulkRunning] = useState(false)

    const toggleSelected = (id: string) => setSelectedIds(prev => {
        const next = new Set(prev)
        if (next.has(id)) next.delete(id); else next.add(id)
        return next
    })
    const exitSelectMode = () => { setSelectMode(false); setSelectedIds(new Set()) }

    const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

    const runBulk = (kind: 'drop10' | 'end', targets: Listing[]) => {
        if (targets.length === 0 || bulkRunning) return
        const n = targets.length
        setConfirmAction(kind === 'drop10'
            ? {
                title: `Drop price 10% on ${n} listing${n !== 1 ? 's' : ''}?`,
                description: 'Each price is revised on eBay immediately.',
                confirmLabel: 'Drop prices',
                destructive: false,
                onConfirm: () => void doRunBulk(kind, targets),
            }
            : {
                title: `End ${n} listing${n !== 1 ? 's' : ''}?`,
                description: "They will be removed from eBay. This can't be undone.",
                confirmLabel: 'End listings',
                destructive: true,
                onConfirm: () => void doRunBulk(kind, targets),
            })
    }

    const doRunBulk = async (kind: 'drop10' | 'end', targets: Listing[]) => {
        setBulkRunning(true)
        const toastId = toast.loading(`Working… 0/${targets.length}`)
        let ok = 0, failedCount = 0
        for (let i = 0; i < targets.length; i++) {
            const l = targets[i]
            try {
                if (kind === 'drop10') {
                    const next = parseFloat((l.price * 0.9).toFixed(2))
                    await apiFetch(`/api/listings/${l.listingId}/price`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ price: next }),
                    })
                    setData(d => d ? { ...d, listings: d.listings.map(x => x.listingId === l.listingId ? { ...x, price: next } : x) } : d)
                } else {
                    await apiFetch(`/api/listings/${l.listingId}/end`, { method: 'POST' })
                    setData(d => d ? { ...d, listings: d.listings.filter(x => x.listingId !== l.listingId) } : d)
                }
                ok++
            } catch {
                failedCount++
            }
            toast.loading(`Working… ${i + 1}/${targets.length}`, { id: toastId })
            // eBay limiter: 5 burst, 2/sec refill — pace sequentially
            if (i < targets.length - 1) await sleep(400)
        }
        toast.dismiss(toastId)
        const verb = kind === 'drop10' ? 'Dropped price on' : 'Ended'
        if (failedCount) toast.warning(`${verb} ${ok} — ${failedCount} failed`)
        else toast.success(`${verb} ${ok} listing${ok !== 1 ? 's' : ''}`)
        setBulkRunning(false)
        exitSelectMode()
    }

    // --- Derive the cockpit view ---
    const activeListings = (data?.listings || []).filter(l => l.status === 'Active' || l.status === 'PUBLISHED')
    const enriched = activeListings.map(l => {
        const age = ageDays(l.startTime)
        return { l, age, tag: staleTag(l.watchCount ?? 0, age) }
    })
    const counts = {
        all: enriched.length,
        dead: enriched.filter(e => e.tag === 'dead').length,
        stale: enriched.filter(e => e.tag === 'stale').length,
        warm: enriched.filter(e => e.tag === 'warm').length,
    }
    const deadCapital = enriched.filter(e => e.tag === 'dead').reduce((s, e) => s + (e.l.price || 0), 0)
    const staleCapital = enriched.filter(e => e.tag === 'stale').reduce((s, e) => s + (e.l.price || 0), 0)

    const q = searchQuery.toLowerCase()
    const shown = enriched
        .filter(e => staleFilter === 'all' || e.tag === staleFilter)
        .filter(e => !q || e.l.title.toLowerCase().includes(q) || e.l.sku.toLowerCase().includes(q))
        .sort((a, b) => TAG_META[a.tag].rank - TAG_META[b.tag].rank || (b.age ?? 0) - (a.age ?? 0))

    const chips: { key: 'all' | StaleTag; label: string; n: number }[] = [
        { key: 'all', label: 'All', n: counts.all },
        { key: 'dead', label: 'Dead', n: counts.dead },
        { key: 'stale', label: 'Stale', n: counts.stale },
        { key: 'warm', label: 'Warm', n: counts.warm },
    ]

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="flex flex-col h-full w-full overflow-hidden"
        >
            {/* Header */}
            <div className="px-4 sm:px-6 py-4 border-b border-stone-200 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 shrink-0 rounded-xl bg-persimmon-50 border border-persimmon-200 flex items-center justify-center text-persimmon-600">
                        <Package size={20} />
                    </div>
                    <div>
                        <h2 className="font-display font-bold text-ink-800 text-lg tracking-tight">Inventory</h2>
                        <div className="flex bg-stone-50 border border-stone-200 rounded-xl p-0.5 mt-1.5 w-fit">
                            {(['active', 'sold'] as const).map(tab => (
                                <button
                                    key={tab}
                                    className={`px-4 min-h-[44px] text-sm font-semibold rounded-lg transition capitalize ${filterStatus === tab ? 'bg-stone-100 text-persimmon-600 shadow-sm' : 'text-stone-500 hover:text-ink-800'}`}
                                    onClick={() => setFilterStatus(tab)}
                                >
                                    {tab}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {filterStatus === 'active' && (
                        <Button
                            variant="outline" size="sm"
                            onClick={() => selectMode ? exitSelectMode() : setSelectMode(true)}
                            className={cn('gap-2 border-stone-200 hover:bg-stone-100 hover:text-ink-800',
                                selectMode ? 'text-persimmon-700 bg-persimmon-50' : 'text-stone-600 bg-paper-card')}
                        >
                            <ListChecks size={16} />
                            <span className="hidden sm:inline">{selectMode ? 'Done' : 'Select'}</span>
                        </Button>
                    )}
                    <Button variant="outline" size="sm" onClick={() => setShowMigration(true)} className="gap-2 text-persimmon-600 bg-paper-card border-stone-200 hover:bg-stone-100 hover:text-ink-800">
                        <Download size={16} />
                        <span className="hidden sm:inline">Import</span>
                    </Button>
                    <Button variant="ghost" size="icon" onClick={fetchListings} disabled={isLoading} aria-label="Refresh listings" title="Refresh" className="text-stone-500 hover:text-ink-800 hover:bg-stone-100">
                        <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
                    </Button>
                    {onClose && (
                        <Button variant="ghost" size="sm" onClick={onClose} className="text-stone-500 hover:text-ink-800 hover:bg-stone-100">Close</Button>
                    )}
                </div>
            </div>

            {filterStatus === 'sold' ? (
                <>
                    <div className="px-4 sm:px-6 py-3 border-b border-stone-200 shrink-0 bg-stone-50/20">
                        <Input placeholder="Search orders…" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
                    </div>
                    <div className="flex-1 overflow-hidden relative">
                        <ScrollArea className="h-full">
                            {ordersLoading ? (
                                <div className="flex items-center justify-center h-64 text-stone-500">
                                    <RefreshCw size={24} className="animate-spin mr-2 text-persimmon-600" />Loading orders…
                                </div>
                            ) : ordersError ? (
                                <div className="flex items-center justify-center h-64 text-rose-600 p-4 gap-2">
                                    <AlertCircle size={20} />{ordersError}
                                </div>
                            ) : orders.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-64 text-stone-500 gap-2">
                                    <ShoppingBag size={32} className="text-stone-300" />No orders in the last 90 days
                                </div>
                            ) : (
                                <div className="divide-y divide-stone-200 px-4 sm:px-6">
                                    {orders
                                        .filter(o => !q || o.orderId.toLowerCase().includes(q) || o.buyer.toLowerCase().includes(q))
                                        .map(order => (
                                            <div key={order.orderId} className="py-3 flex items-center justify-between gap-3 border-b border-stone-200 hover:bg-stone-100 transition px-2 rounded-xl">
                                                <div className="min-w-0">
                                                    <p className="text-sm font-bold text-ink-800 truncate">{order.orderId}</p>
                                                    <p className="text-xs text-stone-500 mt-0.5">{order.buyer} · {order.itemCount} item(s)</p>
                                                </div>
                                                <div className="text-right shrink-0">
                                                    <div className="font-bold text-persimmon-600">${order.total.toFixed(2)}</div>
                                                    <div className="text-xs text-stone-500">{new Date(order.creationDate).toLocaleDateString()}</div>
                                                </div>
                                            </div>
                                        ))}
                                </div>
                            )}
                        </ScrollArea>
                    </div>
                </>
            ) : (
                <>
                    {/* Capital banner */}
                    {deadCapital > 0 && (
                        <button
                            onClick={() => setStaleFilter(staleFilter === 'dead' ? 'all' : 'dead')}
                            className="mx-4 sm:mx-6 mt-3 text-left rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 transition hover:bg-rose-100"
                        >
                            <div className="font-display font-bold text-[20px] tracking-[-0.03em] text-rose-700">
                                ${Math.round(deadCapital).toLocaleString()} tied up
                            </div>
                            <div className="text-xs text-rose-600/90 mt-0.5">
                                {counts.dead} dead {counts.dead === 1 ? 'listing' : 'listings'} (&gt;{DEAD_AGE}d, 0 watchers){staleCapital > 0 ? ` · $${Math.round(staleCapital).toLocaleString()} more going stale` : ''}
                            </div>
                        </button>
                    )}

                    {/* Filter chips */}
                    <div className="px-4 sm:px-6 pt-3 pb-2 flex gap-1.5 flex-wrap shrink-0">
                        {chips.map(c => (
                            <button
                                key={c.key}
                                onClick={() => setStaleFilter(c.key)}
                                className={`px-4 min-h-[44px] rounded-full text-[13px] font-semibold transition-all ${staleFilter === c.key ? 'bg-persimmon-600 text-white shadow-sm' : 'bg-paper-card border border-stone-200 text-stone-500 hover:text-ink-800 hover:bg-stone-100'}`}
                            >
                                {c.label} {c.n}
                            </button>
                        ))}
                    </div>

                    {/* Search */}
                    <div className="px-4 sm:px-6 pb-3 shrink-0">
                        <Input placeholder="Search by title or SKU…" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
                    </div>

                    {/* Bulk action bar */}
                    {selectMode && (() => {
                        const selectable = shown.filter(e => e.l.listingId)
                        const selected = selectable.filter(e => selectedIds.has(e.l.listingId!))
                        const allShownSelected = selectable.length > 0 && selected.length === selectable.length
                        const selectedValue = selected.reduce((s, e) => s + (e.l.price || 0), 0)
                        return (
                            <div className="mx-4 sm:mx-6 mb-2 rounded-2xl bg-paper-card border border-persimmon-200 px-3 py-2 flex items-center gap-2 flex-wrap shrink-0">
                                <button
                                    onClick={() => setSelectedIds(allShownSelected ? new Set() : new Set(selectable.map(e => e.l.listingId!)))}
                                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-stone-600 hover:text-ink-800"
                                >
                                    {allShownSelected ? <CheckSquare size={15} className="text-persimmon-600" /> : <Square size={15} />}
                                    All shown ({selectable.length})
                                </button>
                                <span className="text-xs text-stone-500 ml-auto">
                                    {selected.length} selected · ${Math.round(selectedValue).toLocaleString()}
                                </span>
                                <button
                                    disabled={selected.length === 0 || bulkRunning}
                                    onClick={() => runBulk('drop10', selected.map(e => e.l))}
                                    className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-semibold bg-persimmon-50 text-persimmon-700 border border-persimmon-200 hover:bg-persimmon-100 disabled:opacity-50 transition"
                                >
                                    <TrendingDown size={13} /> Drop 10%
                                </button>
                                <button
                                    disabled={selected.length === 0 || bulkRunning}
                                    onClick={() => runBulk('end', selected.map(e => e.l))}
                                    className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 disabled:opacity-50 transition"
                                >
                                    <XCircle size={13} /> End
                                </button>
                            </div>
                        )
                    })()}

                    {/* Cards */}
                    <div className="flex-1 overflow-hidden relative">
                        <ScrollArea className="h-full">
                            {isLoading ? (
                                <div className="flex items-center justify-center h-64 text-stone-500">
                                    <RefreshCw size={24} className="animate-spin mr-2 text-persimmon-600" />Loading inventory…
                                </div>
                            ) : error ? (
                                <div className="flex items-center justify-center h-64 text-rose-600 p-4 gap-2">
                                    <AlertCircle size={20} />{error}
                                </div>
                            ) : shown.length === 0 ? (
                                <div className="flex items-center justify-center h-64 text-stone-500">
                                    {searchQuery ? 'No matching listings' : staleFilter === 'all' ? 'No active listings' : `No ${staleFilter} listings`}
                                </div>
                            ) : (
                                <div className="px-4 sm:px-6 pb-6 flex flex-col gap-2.5">
                                    {shown.map(e => {
                                        const key = e.l.listingId || e.l.sku
                                        const card = (
                                            <InventoryCard
                                                key={selectMode ? undefined : key}
                                                listing={e.l}
                                                busy={busyById[e.l.listingId || '']}
                                                onDropPrice={dropPrice}
                                                onPromote={promote}
                                                onEnd={endListing}
                                            />
                                        )
                                        if (!selectMode) return card
                                        const isSelected = !!e.l.listingId && selectedIds.has(e.l.listingId)
                                        return (
                                            <div
                                                key={key}
                                                role="checkbox"
                                                aria-checked={isSelected}
                                                tabIndex={0}
                                                onClick={() => e.l.listingId && toggleSelected(e.l.listingId)}
                                                onKeyDown={ev => { if (ev.key === ' ' || ev.key === 'Enter') { ev.preventDefault(); e.l.listingId && toggleSelected(e.l.listingId) } }}
                                                className={cn('relative rounded-2xl cursor-pointer transition',
                                                    isSelected && 'ring-2 ring-persimmon-500')}
                                            >
                                                {/* Card is display-only while selecting */}
                                                <div className="pointer-events-none">{card}</div>
                                                <div className="absolute top-2.5 right-2.5">
                                                    {isSelected
                                                        ? <CheckSquare size={20} className="text-persimmon-600" />
                                                        : <Square size={20} className="text-stone-500" />}
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            )}
                        </ScrollArea>
                    </div>

                    <div className="px-4 sm:px-6 py-2.5 bg-stone-50/20 border-t border-stone-200 flex items-center justify-between text-xs text-stone-500 shrink-0">
                        <span>Showing {shown.length} of {counts.all}</span>
                        <span>eBay · live</span>
                    </div>
                </>
            )}

            <AnimatePresence>
                {showMigration && (
                    <MigrationModal
                        onClose={() => setShowMigration(false)}
                        onSuccess={() => fetchListings()}
                    />
                )}
            </AnimatePresence>

            <Dialog open={confirmAction !== null} onOpenChange={(open) => { if (!open) setConfirmAction(null) }}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{confirmAction?.title}</DialogTitle>
                        <DialogDescription>{confirmAction?.description}</DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="gap-2 sm:gap-2">
                        <Button variant="outline" onClick={() => setConfirmAction(null)}>Cancel</Button>
                        <Button
                            variant={confirmAction?.destructive ? 'destructive' : 'default'}
                            onClick={() => { confirmAction?.onConfirm(); setConfirmAction(null) }}
                        >
                            {confirmAction?.confirmLabel}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </motion.div>
    )
}
