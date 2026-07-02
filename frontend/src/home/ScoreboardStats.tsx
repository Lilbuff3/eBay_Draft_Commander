import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { fetchAnalyticsSummary, fetchJobs, type SalesStats } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'
import { useCountUp } from './useCountUp'

/**
 * Purple Mockup Bento Grid Stats.
 */
export function ScoreboardStats({ days = '30' }: { days?: string }) {
    const { data: summary, isError: analyticsUnavailable } = useQuery<SalesStats>({
        queryKey: ['analytics-summary', days],
        queryFn: () => fetchAnalyticsSummary(days),
        staleTime: 60_000,
    })
    const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs })

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
            {/* Revenue / Earnings (Spans left side on mobile, normal grid on desktop) */}
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="col-span-2 md:col-span-1 row-span-2 md:row-span-1 bg-slate-900/40 backdrop-blur-2xl border border-white/5 shadow-glass hover:shadow-glass-hover rounded-3xl p-4 md:p-5 flex flex-col justify-between relative overflow-hidden transition-colors cursor-pointer">
                <div>
                    <p className="text-xs font-medium text-slate-400 mb-1">Revenue · {days}d{analyticsUnavailable && ' · unavailable'}</p>
                    <p className="text-2xl font-bold text-white tracking-tight">{analyticsUnavailable ? '—' : `$${revAnim.toLocaleString()}`}</p>
                </div>
                {/* Decorative Graph (SVG Line) */}
                <div className="h-12 w-full mt-4 relative">
                    <svg className="absolute bottom-0 w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 40">
                        <path d="M0,30 Q20,10 40,25 T80,10 100,25" fill="none" stroke="#a78bfa" strokeWidth="3" strokeLinecap="round" className="drop-shadow-[0_4px_8px_rgba(167,139,250,0.5)]"/>
                    </svg>
                </div>
            </motion.div>

            {/* Right side container for Live and Queued on mobile, or inline on desktop */}
            <div className="col-span-2 md:col-span-2 grid grid-cols-2 gap-3 h-full content-start md:content-center">
                {/* Live Status */}
                <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="col-span-1 bg-brand-500/80 backdrop-blur-2xl border border-white/10 rounded-full md:rounded-3xl py-3 px-4 md:p-5 flex md:flex-col items-center md:items-start justify-between shadow-[inset_0_1px_0_0_rgba(255,255,255,0.2)] shadow-glow hover:shadow-glow-lg transition-shadow cursor-pointer">
                    <div className="flex items-center gap-2 mb-0 md:mb-2">
                        <span className="w-2 h-2 rounded-full bg-white animate-pulse"></span>
                        <span className="text-sm font-semibold text-white">Live</span>
                    </div>
                    <span className="text-lg md:text-3xl font-bold text-white">{liveAnim}</span>
                </motion.div>

                {/* Queued Status */}
                <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="col-span-1 bg-slate-900/40 backdrop-blur-2xl border border-white/5 rounded-full md:rounded-3xl py-3 px-4 md:p-5 flex md:flex-col items-center md:items-start justify-between shadow-glass hover:shadow-glass-hover transition-shadow cursor-pointer">
                    <div className="flex items-center gap-2 mb-0 md:mb-2">
                        <span className="w-2 h-2 rounded-full bg-slate-500"></span>
                        <span className="text-sm font-semibold text-slate-300">Queued</span>
                    </div>
                    <span className="text-lg md:text-3xl font-bold text-white">{queueAnim}</span>
                </motion.div>
            </div>
        </section>
    )
}
