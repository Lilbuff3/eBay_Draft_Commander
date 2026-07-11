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

    const promote = async (listing: Listing) => {
        const id = listing.listingId
        if (!id) return
        if (!confirm(`Promote "${listing.title}"?\nYou only pay the ad rate when it sells.`)) return
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

    const endListing = async (listing: Listing) => {
        const id = listing.listingId
        if (!id) return
        if (!confirm(`End "${listing.title}"?\nThis removes the live eBay listing. Can't be undone.`)) return
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

    const runBulk = async (kind: 'drop10' | 'end', targets: Listing[]) => {
        if (targets.length === 0 || bulkRunning) return
        const prompt = kind === 'drop10'
            ? `Drop price 10% on ${targets.length} listing${targets.length !== 1 ? 's' : ''}?`
            : `End ${targets.length} listing${targets.length !== 1 ? 's' : ''}?\nThis removes them from eBay. Can't be undone.`
        if (!confirm(prompt)) return
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
            <div className="px-4 sm:px-6 py-4 border-b border-white/5 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-brand-400 shadow-sm animate-pulse">
                        <Package size={20} />
                    </div>
                    <div>
                        <h2 className="font-display font-bold text-white text-lg tracking-tight">Inventory</h2>
                        <div className="flex bg-slate-950/40 border border-white/10 rounded-xl p-0.5 mt-1.5 w-fit">
                            {(['active', 'sold'] as const).map(tab => (
                                <button
                                    key={tab}
                                    className={`px-3 py-0.5 text-xs font-semibold rounded-lg transition capitalize ${filterStatus === tab ? 'bg-slate-800 text-brand-400 shadow-sm' : 'text-slate-400 hover:text-white'}`}
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
                            className={cn('gap-2 border-white/10 hover:bg-slate-800 hover:text-white',
                                selectMode ? 'text-brand-300 bg-brand-500/15' : 'text-slate-300 bg-slate-900/60')}
                        >
                            <ListChecks size={16} />
                            <span className="hidden sm:inline">{selectMode ? 'Done' : 'Select'}</span>
                        </Button>
                    )}
                    <Button variant="outline" size="sm" onClick={() => setShowMigration(true)} className="gap-2 text-brand-400 bg-slate-900/60 border-white/10 hover:bg-slate-800 hover:text-white">
                        <Download size={16} />
                        <span className="hidden sm:inline">Import</span>
                    </Button>
                    <Button variant="ghost" size="icon" onClick={fetchListings} disabled={isLoading} aria-label="Refresh listings" title="Refresh" className="text-slate-400 hover:text-white hover:bg-white/5">
                        <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
                    </Button>
                    {onClose && (
                        <Button variant="ghost" size="sm" onClick={onClose} className="text-slate-400 hover:text-white hover:bg-white/5">Close</Button>
                    )}
                </div>
            </div>

            {filterStatus === 'sold' ? (
                <>
                    <div className="px-4 sm:px-6 py-3 border-b border-white/5 shrink-0 bg-slate-950/20">
                        <Input placeholder="Search orders…" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
                    </div>
                    <div className="flex-1 overflow-hidden relative">
                        <ScrollArea className="h-full">
                            {ordersLoading ? (
                                <div className="flex items-center justify-center h-64 text-slate-400">
                                    <RefreshCw size={24} className="animate-spin mr-2 text-brand-400" />Loading orders…
                                </div>
                            ) : ordersError ? (
                                <div className="flex items-center justify-center h-64 text-rose-400 p-4 gap-2">
                                    <AlertCircle size={20} />{ordersError}
                                </div>
                            ) : orders.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-64 text-slate-500 gap-2">
                                    <ShoppingBag size={32} className="text-slate-800" />No orders in the last 90 days
                                </div>
                            ) : (
                                <div className="divide-y divide-white/5 px-4 sm:px-6">
                                    {orders
                                        .filter(o => !q || o.orderId.toLowerCase().includes(q) || o.buyer.toLowerCase().includes(q))
                                        .map(order => (
                                            <div key={order.orderId} className="py-3 flex items-center justify-between gap-3 border-b border-white/5 hover:bg-white/5 transition px-2 rounded-xl">
                                                <div className="min-w-0">
                                                    <p className="text-sm font-bold text-white truncate">{order.orderId}</p>
                                                    <p className="text-[11px] text-slate-400 mt-0.5">{order.buyer} · {order.itemCount} item(s)</p>
                                                </div>
                                                <div className="text-right shrink-0">
                                                    <div className="font-bold text-brand-400">${order.total.toFixed(2)}</div>
                                                    <div className="text-[11px] text-slate-500">{new Date(order.creationDate).toLocaleDateString()}</div>
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
                            className="mx-4 sm:mx-6 mt-3 text-left rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 transition hover:bg-rose-500/15"
                        >
                            <div className="font-display font-bold text-[20px] tracking-[-0.03em] text-rose-300">
                                ${Math.round(deadCapital).toLocaleString()} tied up
                            </div>
                            <div className="text-[12px] text-rose-400/90 mt-0.5">
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
                                className={`px-3 py-1 rounded-full text-[12px] font-semibold transition-all ${staleFilter === c.key ? 'bg-brand-500 text-white shadow-glow' : 'bg-slate-900/60 border border-white/10 text-slate-400 hover:text-white hover:bg-slate-800'}`}
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
                            <div className="mx-4 sm:mx-6 mb-2 rounded-2xl bg-slate-900/70 border border-brand-500/30 px-3 py-2 flex items-center gap-2 flex-wrap shrink-0">
                                <button
                                    onClick={() => setSelectedIds(allShownSelected ? new Set() : new Set(selectable.map(e => e.l.listingId!)))}
                                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-300 hover:text-white"
                                >
                                    {allShownSelected ? <CheckSquare size={15} className="text-brand-400" /> : <Square size={15} />}
                                    All shown ({selectable.length})
                                </button>
                                <span className="text-xs text-slate-500 ml-auto">
                                    {selected.length} selected · ${Math.round(selectedValue).toLocaleString()}
                                </span>
                                <button
                                    disabled={selected.length === 0 || bulkRunning}
                                    onClick={() => runBulk('drop10', selected.map(e => e.l))}
                                    className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-semibold bg-brand-500/10 text-brand-300 border border-brand-500/20 hover:bg-brand-500/20 disabled:opacity-50 transition"
                                >
                                    <TrendingDown size={13} /> Drop 10%
                                </button>
                                <button
                                    disabled={selected.length === 0 || bulkRunning}
                                    onClick={() => runBulk('end', selected.map(e => e.l))}
                                    className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-semibold bg-rose-500/10 text-rose-300 border border-rose-500/20 hover:bg-rose-500/20 disabled:opacity-50 transition"
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
                                <div className="flex items-center justify-center h-64 text-slate-400">
                                    <RefreshCw size={24} className="animate-spin mr-2 text-brand-400" />Loading inventory…
                                </div>
                            ) : error ? (
                                <div className="flex items-center justify-center h-64 text-rose-400 p-4 gap-2">
                                    <AlertCircle size={20} />{error}
                                </div>
                            ) : shown.length === 0 ? (
                                <div className="flex items-center justify-center h-64 text-slate-500">
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
                                                    isSelected && 'ring-2 ring-brand-500')}
                                            >
                                                {/* Card is display-only while selecting */}
                                                <div className="pointer-events-none">{card}</div>
                                                <div className="absolute top-2.5 right-2.5">
                                                    {isSelected
                                                        ? <CheckSquare size={20} className="text-brand-400" />
                                                        : <Square size={20} className="text-slate-500" />}
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            )}
                        </ScrollArea>
                    </div>

                    <div className="px-4 sm:px-6 py-2.5 bg-slate-950/20 border-t border-white/5 flex items-center justify-between text-xs text-slate-500 shrink-0">
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
        </motion.div>
    )
}
