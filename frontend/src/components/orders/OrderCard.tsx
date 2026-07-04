import { ShoppingBag } from 'lucide-react'
import type { Order } from '@/lib/api'
import { shipTag, shipLabel, SHIP_TAG_META } from '@/lib/orderStatus'

/**
 * One sold order in the Orders cockpit. Read-only: shipping actions happen on
 * eBay; this card exists so a sale is impossible to miss.
 */
export function OrderCard({ order }: { order: Order }) {
    const tag = shipTag(order)
    const meta = SHIP_TAG_META[tag]
    const soldDate = order.creationDate ? new Date(order.creationDate).toLocaleDateString() : '—'

    return (
        <div className="flex items-center gap-3 rounded-2xl border border-stone-100 bg-white px-3.5 py-3 shadow-sm">
            {/* Photo */}
            <div className="w-14 h-14 rounded-xl bg-stone-100 shrink-0 overflow-hidden flex items-center justify-center">
                {order.thumbnailUrl ? (
                    <img src={order.thumbnailUrl} alt="" className="w-full h-full object-cover" loading="lazy" />
                ) : (
                    <ShoppingBag size={20} className="text-stone-300" />
                )}
            </div>

            {/* Title + buyer */}
            <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink-800 truncate">
                    {order.itemTitle || order.orderId}
                </p>
                <p className="text-[11px] text-stone-400 mt-0.5 truncate">
                    {order.buyer} · sold {soldDate}
                    {(order.itemCount ?? 1) > 1 ? ` · ${order.itemCount} items` : ''}
                </p>
                <span className={`inline-block mt-1.5 px-2 py-0.5 rounded-md text-[11px] font-semibold ${meta.chip}`}>
                    {meta.label}{tag !== 'done' ? ` · ${shipLabel(order)}` : ''}
                </span>
            </div>

            {/* Money */}
            <div className="text-right shrink-0">
                <div className="font-semibold text-sage-700">${order.total.toFixed(2)}</div>
                <div className="text-[11px] text-stone-400 mt-0.5">{order.orderId}</div>
            </div>
        </div>
    )
}
