import { useQuery } from '@tanstack/react-query'
import { ShoppingBag, AlertTriangle } from 'lucide-react'
import { fetchOrders } from '@/lib/api'
import { shipTag, shipLabel } from '@/lib/orderStatus'
import { useCommanderStore } from '@/store/useCommanderStore'

/**
 * Orders strip for the dashboard home. Loud when shipping is due, quiet
 * otherwise — the whole point is that a sale can never go unnoticed again.
 */
export function OrderStats() {
    const setActiveTab = useCommanderStore(s => s.setActiveTab)
    const { data } = useQuery({
        queryKey: ['orders'],
        queryFn: () => fetchOrders('90', 100),
        staleTime: 30_000,
        refetchInterval: 60_000,
    })

    const orders = data?.orders ?? []
    const tagged = orders.map(o => ({ o, tag: shipTag(o) }))
    const overdue = tagged.filter(t => t.tag === 'overdue')
    const urgent = tagged.filter(t => t.tag === 'urgent')
    const pending = tagged.filter(t => t.tag === 'pending')
    const needsShipping = overdue.length + urgent.length + pending.length

    if (needsShipping === 0) return null

    const hot = overdue.length + urgent.length > 0
    const worst = [...overdue, ...urgent, ...pending][0]

    return (
        <button
            onClick={() => setActiveTab('orders')}
            className={`w-full text-left rounded-3xl border px-4 py-4 flex items-center gap-3 transition shadow-sm hover:shadow-md ${
                hot
                    ? 'border-red-300 bg-red-50 hover:bg-red-100'
                    : 'border-stone-200 bg-paper-card hover:bg-stone-50'
            }`}
        >
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${hot ? 'bg-red-100 text-red-600' : 'bg-stone-100 text-stone-500'}`}>
                {hot ? <AlertTriangle size={20} /> : <ShoppingBag size={20} />}
            </div>
            <div className="min-w-0">
                <div className={`font-display font-bold text-[16px] tracking-tight ${hot ? 'text-red-800' : 'text-ink-800'}`}>
                    {needsShipping} {needsShipping === 1 ? 'order needs' : 'orders need'} shipping
                    {overdue.length > 0 ? ` — ${overdue.length} overdue` : ''}
                </div>
                <div className={`text-sm mt-0.5 truncate ${hot ? 'text-red-700' : 'text-stone-500'}`}>
                    {worst ? `${worst.o.itemTitle ?? worst.o.orderId} · ${shipLabel(worst.o)}` : ''} · tap to view
                </div>
            </div>
        </button>
    )
}
