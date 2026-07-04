/**
 * Ship-deadline signal for the Orders cockpit.
 *
 * Mirrors lib/staleness.ts: derive a tag from raw order fields, expose chip
 * styling + rank for worst-first sorting.
 *
 *   🔴 Overdue — not shipped and past shipByDate (eBay late-shipment defect risk)
 *   🟠 Urgent  — not shipped, due within URGENT_HOURS
 *   ⚪ To ship — not shipped, deadline further out (or unknown)
 *   🟢 Done    — fulfilled
 */
import type { Order } from '@/lib/api'

export type ShipTag = 'overdue' | 'urgent' | 'pending' | 'done'

export const URGENT_HOURS = 24

export function hoursUntil(iso?: string | null): number | null {
    if (!iso) return null
    const t = Date.parse(iso)
    if (isNaN(t)) return null
    return (t - Date.now()) / 3_600_000
}

export function shipTag(order: Order): ShipTag {
    if (order.status === 'FULFILLED') return 'done'
    const h = hoursUntil(order.shipByDate)
    if (h == null) return 'pending'
    if (h < 0) return 'overdue'
    if (h <= URGENT_HOURS) return 'urgent'
    return 'pending'
}

export const SHIP_TAG_META: Record<ShipTag, { label: string; chip: string; rank: number }> = {
    overdue: { label: 'Overdue', chip: 'bg-red-100 text-red-700', rank: 0 },
    urgent: { label: 'Due soon', chip: 'bg-amber-100 text-amber-700', rank: 1 },
    pending: { label: 'To ship', chip: 'bg-stone-100 text-stone-500', rank: 2 },
    done: { label: 'Shipped', chip: 'bg-sage-100 text-sage-700', rank: 3 },
}

/** "3d late" / "due in 5h" / "due in 2d" / "shipped" / "—" */
export function shipLabel(order: Order): string {
    const tag = shipTag(order)
    if (tag === 'done') return 'shipped'
    const h = hoursUntil(order.shipByDate)
    if (h == null) return '—'
    if (h < 0) {
        const d = Math.floor(-h / 24)
        return d >= 1 ? `${d}d late` : `${Math.ceil(-h)}h late`
    }
    return h <= 48 ? `due in ${Math.max(1, Math.round(h))}h` : `due in ${Math.round(h / 24)}d`
}
