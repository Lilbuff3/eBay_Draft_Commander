import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, Wallet } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { cn } from '@/lib/utils'

interface LedgerWeek {
    week_start: string
    revenue: number
    fees: number
    ship: number
    cogs: number
    net: number
    sold_count: number
    missing_cogs: number
}

interface LedgerSummary {
    weeks: LedgerWeek[]
    totals: { revenue: number; net: number; sold_count: number; missing_cogs: number }
}

interface LedgerItem {
    order_id: string
    title: string | null
    sale_total: number
    sold_at: string | null
    fees_est: number | null
    ship_est: number | null
    cogs: number | null
    net: number | null
    roi: number | null
    days_to_sell: number | null
    thumbnailUrl: string | null
}

const money = (n: number | null | undefined) =>
    n === null || n === undefined ? '—' : `$${n.toFixed(2)}`

function WeekCard({ week, label }: { week: LedgerWeek | undefined; label: string }) {
    return (
        <div className="rounded-2xl bg-white/5 border border-white/10 p-4">
            <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">{label}</div>
            <div className={cn('text-2xl font-bold',
                (week?.net ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                {money(week?.net ?? 0)}
            </div>
            <div className="text-xs text-slate-400 mt-1">
                {week ? `${week.sold_count} sold · ${money(week.revenue)} gross` : 'no sales'}
            </div>
            {week && week.missing_cogs > 0 && (
                <div className="text-xs text-amber-400 mt-1">
                    {week.missing_cogs} missing cost — net understated
                </div>
            )}
        </div>
    )
}

function CogsCell({ item, onSaved }: { item: LedgerItem; onSaved: () => void }) {
    const [editing, setEditing] = useState(false)
    const [value, setValue] = useState('')
    const save = async () => {
        const v = parseFloat(value)
        if (isNaN(v) || v < 0) { setEditing(false); return }
        try {
            await apiFetch(`/api/ledger/sales/${item.order_id}/cogs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cogs: v }),
            })
            onSaved()
        } finally {
            setEditing(false)
        }
    }
    if (item.cogs !== null && !editing) {
        return (
            <button className="text-slate-300 hover:text-white" onClick={() => { setValue(String(item.cogs)); setEditing(true) }}>
                {money(item.cogs)}
            </button>
        )
    }
    if (!editing) {
        return (
            <button className="text-amber-400 underline decoration-dotted" onClick={() => setEditing(true)}>
                add cost
            </button>
        )
    }
    return (
        <input
            autoFocus
            inputMode="decimal"
            className="w-16 rounded bg-white/10 border border-white/20 px-1 py-0.5 text-right text-white"
            value={value}
            onChange={e => setValue(e.target.value)}
            onBlur={save}
            onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
        />
    )
}

export function Profit() {
    const [summary, setSummary] = useState<LedgerSummary | null>(null)
    const [items, setItems] = useState<LedgerItem[]>([])
    const [loading, setLoading] = useState(false)

    const load = useCallback(async () => {
        setLoading(true)
        try {
            // Fetch orders first so the sweep runs and the ledger is fresh
            await apiFetch('/api/orders?days=30').catch(() => null)
            const [s, i] = await Promise.all([
                apiFetch<LedgerSummary>('/api/ledger/summary?weeks=8'),
                apiFetch<{ items: LedgerItem[] }>('/api/ledger/items?limit=200'),
            ])
            setSummary(s)
            setItems(i.items)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { void load() }, [load])

    const missing = summary?.totals.missing_cogs ?? 0

    return (
        <div className="h-full overflow-auto p-4 md:p-6">
            <div className="mx-auto max-w-3xl space-y-4 pb-24">
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <h1 className="text-2xl font-display font-bold text-white tracking-tight flex items-center gap-2">
                            <Wallet size={22} /> Profit
                        </h1>
                        <p className="text-slate-400 text-sm">Real net after fees, shipping and cost of goods</p>
                    </div>
                    <button
                        onClick={() => void load()}
                        className="rounded-xl bg-white/10 border border-white/10 p-2 text-slate-300 hover:text-white"
                        aria-label="Refresh"
                    >
                        <RefreshCw size={16} className={cn(loading && 'animate-spin')} />
                    </button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                    <WeekCard week={summary?.weeks[0]} label="This week" />
                    <WeekCard week={summary?.weeks[1]} label="Last week" />
                </div>

                {missing > 0 && (
                    <div className="rounded-xl bg-amber-500/10 border border-amber-500/30 px-3 py-2 text-sm text-amber-300">
                        {missing} sold item{missing !== 1 ? 's' : ''} missing cost — tap “add cost” below to fix your numbers
                    </div>
                )}

                <div className="space-y-2">
                    {items.map(item => (
                        <div key={item.order_id} className="rounded-2xl bg-white/5 border border-white/10 p-3 flex items-center gap-3">
                            {item.thumbnailUrl
                                ? <img src={item.thumbnailUrl} alt="" className="w-12 h-12 rounded-lg object-cover shrink-0" />
                                : <div className="w-12 h-12 rounded-lg bg-white/10 shrink-0" />}
                            <div className="min-w-0 flex-1">
                                <div className="text-sm text-white truncate">{item.title || item.order_id}</div>
                                <div className="text-xs text-slate-400">
                                    {money(item.sale_total)} sale
                                    {item.days_to_sell !== null && ` · ${item.days_to_sell}d to sell`}
                                    {item.roi !== null && ` · ${Math.round(item.roi * 100)}% ROI`}
                                </div>
                            </div>
                            <div className="text-right shrink-0">
                                <div className={cn('text-sm font-semibold',
                                    item.net === null ? 'text-slate-500'
                                        : item.net >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                                    {item.net === null ? 'net ?' : money(item.net)}
                                </div>
                                <div className="text-xs">
                                    <CogsCell item={item} onSaved={() => void load()} />
                                </div>
                            </div>
                        </div>
                    ))}
                    {!loading && items.length === 0 && (
                        <div className="text-center text-slate-500 text-sm py-10">
                            No sales recorded yet — sales appear after your next order sync
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
