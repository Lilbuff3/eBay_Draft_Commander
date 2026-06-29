import { useQuery } from '@tanstack/react-query'
import { TrendingUp, Package, ShoppingBag, Clock, ChevronUp } from 'lucide-react'
import { fetchAnalyticsSummary, fetchStatus, fetchJobs, type SalesStats } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'
import { useCountUp } from './useCountUp'

/**
 * Redesigned scoreboard — four uniform, quiet stat cards.
 *
 * Replaces the old ScoreboardBanner. Pure data sources:
 *   - revenue / sold        ← /api/analytics/summary  (fetchAnalyticsSummary)
 *   - live on eBay          ← summary.active_listings_count (fallback: jobs in "live" bucket)
 *   - time saved            ← ESTIMATE: completed jobs × MINUTES_PER_ITEM.
 *                             Replace with a real backend field when available
 *                             (see README → Backend touchpoints).
 */

const MINUTES_PER_ITEM = 12 // tune to your measured average

function StatCard({
    label, value, sub, accent = false,
}: { label: string; value: string; sub?: string; accent?: boolean }) {
    return (
        <div className="bg-white border border-ink-900/[0.07] rounded-2xl px-4 py-4 shadow-[0_1px_2px_rgba(34,28,22,0.03)]">
            <span className="text-xs font-semibold text-stone-500">{label}</span>
            <div className="font-display font-bold text-[28px] tracking-[-0.04em] mt-2 text-ink-800">{value}</div>
            {sub && (
                <div className={`flex items-center gap-1 text-[11.5px] font-semibold mt-1 ${accent ? 'text-sage-700' : 'text-stone-400'}`}>
                    {accent && <ChevronUp className="w-3 h-3" strokeWidth={2.6} />}
                    {sub}
                </div>
            )}
        </div>
    )
}

export function ScoreboardStats({ days = '30' }: { days?: string }) {
    const { data: summary } = useQuery<SalesStats>({
        queryKey: ['analytics-summary', days],
        queryFn: () => fetchAnalyticsSummary(days),
        staleTime: 60_000,
    })
    const { data: status } = useQuery({ queryKey: ['status'], queryFn: fetchStatus, refetchInterval: 5000 })
    const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs })

    const revenue = summary?.total_revenue ?? 0
    const live = summary?.active_listings_count ?? jobs.filter(j => getStatusBucket(j.status) === 'live').length
    const sold = summary?.items_sold ?? 0
    const completed = status?.stats.completed ?? jobs.filter(j => getStatusBucket(j.status) === 'live').length
    const minutesSaved = completed * MINUTES_PER_ITEM

    // count-up animations (background-tab-safe)
    const revAnim = useCountUp(Math.round(revenue))
    const liveAnim = useCountUp(live)
    const soldAnim = useCountUp(sold)
    const minAnim = useCountUp(minutesSaved)
    const savedLabel = `${Math.floor(minAnim / 60)}h ${minAnim % 60}m`

    return (
        <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard label="Revenue · 30d" value={`$${revAnim.toLocaleString()}`} sub="vs prior period" accent />
            <StatCard label="Live on eBay" value={String(liveAnim)} sub="active listings" />
            <StatCard label="Sold · 30d" value={String(soldAnim)} sub="orders shipped" />
            <StatCard label="Time saved" value={savedLabel} sub="vs manual listing" />
        </section>
    )
}

/* Icons kept imported for teams that prefer the chip variant; remove if unused. */
void TrendingUp; void Package; void ShoppingBag; void Clock
