import { useState } from 'react'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { ShoppingBag, RefreshCw, AlertCircle } from 'lucide-react'
import { fetchOrders, type Order } from '@/lib/api'
import { shipTag, SHIP_TAG_META, type ShipTag } from '@/lib/orderStatus'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
import { OrderCard } from '@/components/orders/OrderCard'

/**
 * Orders cockpit — sold items with ship-by deadlines, worst-first.
 * Read-only: the point is that a sale can never go unnoticed again.
 */
export function Orders() {
    const [searchQuery, setSearchQuery] = useState('')
    const [filter, setFilter] = useState<'all' | ShipTag>('all')

    const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
        queryKey: ['orders'],
        queryFn: () => fetchOrders('90', 100),
        refetchInterval: 30_000,
    })

    const enriched = (data?.orders ?? []).map(o => ({ o, tag: shipTag(o) }))
    const counts = {
        all: enriched.length,
        overdue: enriched.filter(e => e.tag === 'overdue').length,
        urgent: enriched.filter(e => e.tag === 'urgent').length,
        pending: enriched.filter(e => e.tag === 'pending').length,
        done: enriched.filter(e => e.tag === 'done').length,
    }
    const toShip = counts.overdue + counts.urgent + counts.pending

    const q = searchQuery.toLowerCase()
    const matches = (o: Order) =>
        !q ||
        (o.itemTitle ?? '').toLowerCase().includes(q) ||
        o.buyer.toLowerCase().includes(q) ||
        o.orderId.toLowerCase().includes(q)

    const shown = enriched
        .filter(e => filter === 'all' || e.tag === filter)
        .filter(e => matches(e.o))
        .sort(
            (a, b) =>
                SHIP_TAG_META[a.tag].rank - SHIP_TAG_META[b.tag].rank ||
                Date.parse(a.o.shipByDate ?? a.o.creationDate) - Date.parse(b.o.shipByDate ?? b.o.creationDate)
        )

    const chips: { key: 'all' | ShipTag; label: string; n: number }[] = [
        { key: 'all', label: 'All', n: counts.all },
        { key: 'overdue', label: 'Overdue', n: counts.overdue },
        { key: 'urgent', label: 'Due soon', n: counts.urgent },
        { key: 'pending', label: 'To ship', n: counts.pending },
        { key: 'done', label: 'Shipped', n: counts.done },
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
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-persimmon-100 border border-persimmon-200 flex items-center justify-center text-persimmon-600 shadow-sm">
                        <ShoppingBag size={20} />
                    </div>
                    <div>
                        <h2 className="font-display font-bold text-ink-800 text-lg tracking-tight">Orders</h2>
                        <p className="text-[11px] text-stone-500 mt-0.5">Sold on eBay · last 90 days</p>
                    </div>
                </div>
                <Button variant="ghost" size="icon" onClick={() => refetch()} disabled={isFetching} aria-label="Refresh orders" title="Refresh" className="text-stone-500 hover:text-ink-800 hover:bg-stone-100">
                    <RefreshCw size={16} className={isFetching ? 'animate-spin' : ''} />
                </Button>
            </div>

            {/* Ship-now banner */}
            {counts.overdue + counts.urgent > 0 && (
                <button
                    onClick={() => setFilter(filter === 'overdue' ? 'all' : 'overdue')}
                    className="mx-4 sm:mx-6 mt-3 text-left rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 transition hover:bg-rose-100"
                >
                    <div className="font-display font-bold text-[20px] tracking-[-0.03em] text-rose-700">
                        {counts.overdue + counts.urgent} {counts.overdue + counts.urgent === 1 ? 'order needs' : 'orders need'} shipping
                    </div>
                    <div className="text-[12px] text-rose-600/90 mt-0.5">
                        {counts.overdue > 0 ? `${counts.overdue} past the ship-by date — late shipments hurt your seller rating` : 'Due within 24 hours'}
                    </div>
                </button>
            )}

            {/* Filter chips */}
            <div className="px-4 sm:px-6 pt-3 pb-2 flex gap-1.5 flex-wrap shrink-0">
                {chips.map(c => (
                    <button
                        key={c.key}
                        onClick={() => setFilter(c.key)}
                        className={`px-4 min-h-[44px] rounded-full text-[13px] font-semibold transition-all ${filter === c.key ? 'bg-persimmon-600 text-white shadow-sm' : 'bg-paper-card border border-stone-200 text-stone-500 hover:text-ink-800 hover:bg-stone-100'}`}
                    >
                        {c.label} {c.n}
                    </button>
                ))}
            </div>

            {/* Search */}
            <div className="px-4 sm:px-6 pb-3 shrink-0">
                <Input placeholder="Search by item, buyer, or order ID…" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
            </div>

            {/* Cards */}
            <div className="flex-1 overflow-hidden relative">
                <ScrollArea className="h-full">
                    {isLoading ? (
                        <div className="flex items-center justify-center h-64 text-stone-500">
                            <RefreshCw size={24} className="animate-spin mr-2 text-persimmon-600" />Loading orders…
                        </div>
                    ) : isError ? (
                        <div className="flex items-center justify-center h-64 text-rose-600 p-4 gap-2">
                            <AlertCircle size={20} />{error instanceof Error ? error.message : 'Failed to load orders'}
                        </div>
                    ) : shown.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-64 text-stone-500 gap-2">
                            <ShoppingBag size={32} className="text-stone-300" />
                            {searchQuery ? 'No matching orders' : filter === 'all' ? 'No orders in the last 90 days' : `Nothing ${SHIP_TAG_META[filter as ShipTag]?.label.toLowerCase() ?? ''}`}
                        </div>
                    ) : (
                        <div className="px-4 sm:px-6 pb-6 pt-1 flex flex-col gap-2.5">
                            {shown.map(e => (
                                <OrderCard key={e.o.orderId} order={e.o} />
                            ))}
                        </div>
                    )}
                </ScrollArea>
            </div>

            {/* Footer */}
            <div className="px-4 sm:px-6 py-2.5 bg-stone-50/20 border-t border-stone-200 flex items-center justify-between text-xs text-stone-500 shrink-0">
                <span>Showing {shown.length} of {counts.all}</span>
                <span>{toShip > 0 ? `${toShip} to ship` : 'all shipped'} · eBay live</span>
            </div>
        </motion.div>
    )
}
