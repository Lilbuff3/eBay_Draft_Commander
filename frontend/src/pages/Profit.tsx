import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, RefreshCw, Wallet } from 'lucide-react'
import { toast } from 'sonner'
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

interface PerfRow {
    listed: number
    sold: number
    sell_through: number | null
    revenue: number
    net: number | null
    roi: number | null
    avg_days: number | null
}

interface Performance {
    days: number
    listed: number
    sold: number
    sell_through_rate: number | null
    avg_days_to_sell: number | null
    median_days_to_sell: number | null
    by_category: (PerfRow & { category: string })[]
    by_source: (PerfRow & { source: string })[]
}

const money = (n: number | null | undefined) =>
    n === null || n === undefined ? '—' : `$${n.toFixed(2)}`

const pct = (n: number | null | undefined) =>
    n === null || n === undefined ? '—' : `${Math.round(n * 100)}%`

function PerfTable({ rows, label }: {
    rows: (PerfRow & { category?: string; source?: string })[]
    label: string
}) {
    if (rows.length === 0) return null
    return (
        <div className="rounded-2xl bg-stone-100 border border-stone-200 p-3">
            <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">{label}</div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="text-xs text-stone-500 text-left">
                            <th className="pb-1 pr-2 font-normal">{label}</th>
                            <th className="pb-1 pr-2 font-normal text-right">Sold/Listed</th>
                            <th className="pb-1 pr-2 font-normal text-right">Sell-thru</th>
                            <th className="pb-1 pr-2 font-normal text-right">Revenue</th>
                            <th className="pb-1 pr-2 font-normal text-right">Net</th>
                            <th className="pb-1 font-normal text-right">Days</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((r, i) => (
                            <tr key={i} className="text-ink-800">
                                <td className="py-1 pr-2 truncate max-w-[10rem]">{r.category ?? r.source}</td>
                                <td className="py-1 pr-2 text-right text-stone-600">{r.sold}/{r.listed}</td>
                                <td className="py-1 pr-2 text-right text-stone-600">{pct(r.sell_through)}</td>
                                <td className="py-1 pr-2 text-right">{money(r.revenue)}</td>
                                <td className={cn('py-1 pr-2 text-right font-medium',
                                    r.net === null ? 'text-stone-400'
                                        : r.net >= 0 ? 'text-emerald-600' : 'text-red-600')}>
                                    {r.net === null ? '?' : money(r.net)}
                                </td>
                                <td className="py-1 text-right text-stone-600">
                                    {r.avg_days === null ? '—' : `${Math.round(r.avg_days)}d`}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

function WeekCard({ week, label }: { week: LedgerWeek | undefined; label: string }) {
    return (
        <div className="rounded-2xl bg-stone-100 border border-stone-200 p-4">
            <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">{label}</div>
            <div className={cn('text-2xl font-bold',
                (week?.net ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-600')}>
                {money(week?.net ?? 0)}
            </div>
            <div className="text-xs text-stone-500 mt-1">
                {week ? `${week.sold_count} sold · ${money(week.revenue)} gross` : 'no sales'}
            </div>
            {week && week.missing_cogs > 0 && (
                <div className="text-xs text-amber-600 mt-1">
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
        } catch (e) {
            toast.error(e instanceof Error ? e.message : 'Failed to save cost')
        } finally {
            setEditing(false)
        }
    }
    if (item.cogs !== null && !editing) {
        return (
            <button
                className="min-h-[44px] px-2 -mx-2 rounded-lg text-stone-600 hover:bg-stone-100 hover:text-ink-800"
                onClick={() => { setValue(String(item.cogs)); setEditing(true) }}
            >
                {money(item.cogs)}
            </button>
        )
    }
    if (!editing) {
        return (
            <button
                className="min-h-[44px] px-2 -mx-2 rounded-lg text-amber-700 underline decoration-dotted hover:bg-amber-50"
                onClick={() => setEditing(true)}
            >
                add cost
            </button>
        )
    }
    return (
        <input
            autoFocus
            inputMode="decimal"
            className="w-16 rounded bg-stone-50 border border-stone-300 px-1 py-0.5 text-right text-ink-800"
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
    const [perf, setPerf] = useState<Performance | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const load = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            // Fetch orders first so the sweep runs and the ledger is fresh
            await apiFetch('/api/orders?days=30').catch(() => null)
            const [s, i, p] = await Promise.all([
                apiFetch<LedgerSummary>('/api/ledger/summary?weeks=8'),
                apiFetch<{ items: LedgerItem[] }>('/api/ledger/items?limit=200'),
                apiFetch<Performance>('/api/ledger/performance?days=90').catch(() => null),
            ])
            setSummary(s)
            setItems(i.items)
            setPerf(p)
        } catch (e) {
            // A failed load must never render as "$0.00, no sales"
            setError(e instanceof Error ? e.message : 'Failed to load ledger')
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
                        <h1 className="text-2xl font-display font-bold text-ink-800 tracking-tight flex items-center gap-2">
                            <Wallet size={22} /> Profit
                        </h1>
                        <p className="text-stone-500 text-sm">Real net after fees, shipping and cost of goods</p>
                    </div>
                    <button
                        onClick={() => void load()}
                        className="grid size-11 shrink-0 place-items-center rounded-xl bg-stone-100 border border-stone-200 text-stone-600 hover:bg-stone-200 hover:text-ink-800"
                        aria-label="Refresh"
                    >
                        <RefreshCw size={16} className={cn(loading && 'animate-spin')} />
                    </button>
                </div>

                {error && (
                    <div className="rounded-xl bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700 flex items-center gap-2">
                        <AlertCircle size={16} className="shrink-0" />
                        <span className="flex-1">{error}</span>
                        <button onClick={() => void load()} className="underline shrink-0">Retry</button>
                    </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                    <WeekCard week={summary?.weeks[0]} label="This week" />
                    <WeekCard week={summary?.weeks[1]} label="Last week" />
                </div>

                {missing > 0 && (
                    <div className="rounded-xl bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-700">
                        {missing} sold item{missing !== 1 ? 's' : ''} missing cost — tap “add cost” below to fix your numbers
                    </div>
                )}

                {perf && perf.listed > 0 && (
                    <>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="rounded-2xl bg-stone-100 border border-stone-200 p-4">
                                <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">
                                    Sell-through · {perf.days}d
                                </div>
                                <div className="text-2xl font-bold text-ink-800">{pct(perf.sell_through_rate)}</div>
                                <div className="text-xs text-stone-500 mt-1">{perf.sold} of {perf.listed} listed</div>
                            </div>
                            <div className="rounded-2xl bg-stone-100 border border-stone-200 p-4">
                                <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">Days to sell</div>
                                <div className="text-2xl font-bold text-ink-800">
                                    {perf.median_days_to_sell === null ? '—' : `${Math.round(perf.median_days_to_sell)}d`}
                                </div>
                                <div className="text-xs text-stone-500 mt-1">
                                    {perf.avg_days_to_sell === null ? 'no sales matched' : `avg ${Math.round(perf.avg_days_to_sell)}d`}
                                </div>
                            </div>
                        </div>
                        <PerfTable rows={perf.by_category} label="Category" />
                        <PerfTable rows={perf.by_source} label="Source" />
                    </>
                )}

                <div className="space-y-2">
                    {items.map(item => (
                        <div key={item.order_id} className="rounded-2xl bg-stone-100 border border-stone-200 p-3 flex items-center gap-3">
                            {item.thumbnailUrl
                                ? <img src={item.thumbnailUrl} alt="" className="w-12 h-12 rounded-lg object-cover shrink-0" />
                                : <div className="w-12 h-12 rounded-lg bg-stone-100 shrink-0" />}
                            <div className="min-w-0 flex-1">
                                <div className="text-sm text-ink-800 truncate">{item.title || item.order_id}</div>
                                <div className="text-xs text-stone-500">
                                    {money(item.sale_total)} sale
                                    {item.days_to_sell !== null && ` · ${item.days_to_sell}d to sell`}
                                    {item.roi !== null && ` · ${Math.round(item.roi * 100)}% ROI`}
                                </div>
                            </div>
                            <div className="text-right shrink-0">
                                <div className={cn('text-sm font-semibold',
                                    item.net === null ? 'text-stone-500'
                                        : item.net >= 0 ? 'text-emerald-600' : 'text-red-600')}>
                                    {item.net === null ? 'net ?' : money(item.net)}
                                </div>
                                <div className="text-xs">
                                    <CogsCell item={item} onSaved={() => void load()} />
                                </div>
                            </div>
                        </div>
                    ))}
                    {!loading && !error && items.length === 0 && (
                        <div className="text-center text-stone-500 text-sm py-10">
                            No sales recorded yet — sales appear after your next order sync
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
