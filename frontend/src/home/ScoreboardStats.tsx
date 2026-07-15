import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { RefreshCw } from 'lucide-react'
import { fetchAnalyticsSummary, fetchJobs, type SalesStats } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useCountUp } from './useCountUp'

/**
 * Money strip. Revenue and Live are drill-downs (Profit / Inventory tabs).
 * Queued is a plain readout — the jobs it counts are rendered in the Workspace
 * directly below it, so it deliberately carries no tap affordance.
 */
export function ScoreboardStats({ days = '30' }: { days?: string }) {
    const { data: summary, isError: analyticsUnavailable, isPending: analyticsPending, refetch } = useQuery<SalesStats>({
        queryKey: ['analytics-summary', days],
        queryFn: () => fetchAnalyticsSummary(days),
        staleTime: 60_000,
    })
    const { data: jobs = [], isPending: jobsPending } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs })
    const setActiveTab = useCommanderStore(s => s.setActiveTab)

    // Never render a number we don't have yet: defaulting to 0 while the query is
    // in flight makes a money dashboard read "$0 / 0 live" on every cold load.
    const pending = analyticsPending || jobsPending

    const revenue = summary?.total_revenue ?? 0
    const live = summary?.active_listings_count ?? jobs.filter(j => getStatusBucket(j.status) === 'live').length

    const queuedCount = jobs.filter(j => {
        const b = getStatusBucket(j.status)
        return b === 'working' || b === 'needs_you'
    }).length

    // count-up animations (background-tab-safe)
    const revAnim = useCountUp(Math.round(revenue))
    const liveAnim = useCountUp(live)
    const queueAnim = useCountUp(queuedCount)

    return (
        <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-3 w-full">
            {/* Revenue → Profit tab */}
            <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setActiveTab('profit')}
                aria-label={`Revenue over ${days} days — open Profit`}
                className="col-span-2 md:col-span-1 row-span-2 md:row-span-1 text-left bg-paper-card border border-stone-200 shadow-sm hover:shadow-md rounded-3xl p-4 md:p-5 flex flex-col justify-between relative overflow-hidden transition-shadow cursor-pointer"
            >
                <div>
                    <p className="text-xs font-medium text-stone-500 mb-1">Revenue · {days}d</p>
                    {analyticsPending ? (
                        <div className="h-8 w-28 rounded-lg bg-stone-200 animate-pulse" />
                    ) : (
                        <p className="text-2xl font-bold text-ink-800 tracking-tight">
                            {analyticsUnavailable ? '—' : `$${revAnim.toLocaleString()}`}
                        </p>
                    )}
                </div>

                {analyticsUnavailable ? (
                    <span
                        role="button"
                        tabIndex={0}
                        onClick={(e) => { e.stopPropagation(); refetch() }}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); refetch() } }}
                        className="mt-4 inline-flex items-center gap-1.5 self-start rounded-lg border border-stone-200 px-2.5 py-1.5 text-xs font-medium text-stone-600 hover:bg-stone-100 transition-colors"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                        Couldn’t load — retry
                    </span>
                ) : (
                    <p className="mt-4 text-xs font-medium text-stone-500">Tap for the profit breakdown</p>
                )}
            </motion.button>

            {/* Live + Queued */}
            <div className="col-span-2 md:col-span-2 grid grid-cols-2 gap-3 h-full content-start md:content-center">
                {/* Live → Inventory tab */}
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setActiveTab('inventory')}
                    aria-label={`${live} live listings — open Inventory`}
                    className="col-span-1 bg-persimmon-600 border border-persimmon-700 rounded-full md:rounded-3xl py-3 px-4 md:p-5 flex md:flex-col items-center md:items-start justify-between shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                >
                    <div className="flex items-center gap-2 mb-0 md:mb-2">
                        <span className="w-2 h-2 rounded-full bg-white animate-pulse"></span>
                        <span className="text-sm font-semibold text-white">Live</span>
                    </div>
                    {pending
                        ? <span className="h-7 w-8 rounded bg-white/40 animate-pulse" />
                        : <span className="text-lg md:text-3xl font-bold text-white">{liveAnim}</span>}
                </motion.button>

                {/* Queued — readout only; the Workspace below lists these jobs. */}
                <div className="col-span-1 bg-paper-card border border-stone-200 rounded-full md:rounded-3xl py-3 px-4 md:p-5 flex md:flex-col items-center md:items-start justify-between shadow-sm">
                    <div className="flex items-center gap-2 mb-0 md:mb-2">
                        <span className="w-2 h-2 rounded-full bg-stone-400"></span>
                        <span className="text-sm font-semibold text-stone-600">Queued</span>
                    </div>
                    {jobsPending
                        ? <span className="h-7 w-8 rounded bg-stone-200 animate-pulse" />
                        : <span className="text-lg md:text-3xl font-bold text-ink-800">{queueAnim}</span>}
                </div>
            </div>
        </section>
    )
}
