import { useQuery } from '@tanstack/react-query'
import { fetchAnalyticsSummary, fetchJobs, type SalesStats } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'
import { useCountUp } from './useCountUp'

/**
 * Purple Mockup Bento Grid Stats.
 */
export function ScoreboardStats({ days = '30' }: { days?: string }) {
    const { data: summary } = useQuery<SalesStats>({
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
            <div className="col-span-2 md:col-span-1 row-span-2 md:row-span-1 bg-slate-900/40 backdrop-blur-xl border border-slate-800/60 rounded-3xl p-4 md:p-5 flex flex-col justify-between relative overflow-hidden transition-all hover:bg-slate-800/40">
                <div>
                    <p className="text-xs font-medium text-slate-400 mb-1">Revenue · {days}d</p>
                    <p className="text-2xl font-bold text-white tracking-tight">${revAnim.toLocaleString()}</p>
                </div>
                {/* Decorative Graph (SVG Line) */}
                <div className="h-12 w-full mt-4 relative">
                    <svg className="absolute bottom-0 w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 40">
                        <path d="M0,30 Q20,10 40,25 T80,10 100,25" fill="none" stroke="#a78bfa" strokeWidth="3" strokeLinecap="round" className="drop-shadow-[0_4px_8px_rgba(167,139,250,0.5)]"/>
                    </svg>
                </div>
            </div>

            {/* Right side container for Live and Queued on mobile, or inline on desktop */}
            <div className="col-span-2 md:col-span-2 grid grid-cols-2 gap-3 h-full content-start md:content-center">
                {/* Live Status */}
                <div className="col-span-1 bg-brand-600/90 backdrop-blur-md border border-brand-500/50 rounded-full md:rounded-3xl py-3 px-4 md:p-5 flex md:flex-col items-center md:items-start justify-between shadow-glow transition-all hover:bg-brand-500/90 hover:scale-[1.02] cursor-pointer">
                    <div className="flex items-center gap-2 mb-0 md:mb-2">
                        <span className="w-2 h-2 rounded-full bg-white animate-pulse"></span>
                        <span className="text-sm font-semibold text-white">Live</span>
                    </div>
                    <span className="text-lg md:text-3xl font-bold text-white">{liveAnim}</span>
                </div>

                {/* Queued Status */}
                <div className="col-span-1 bg-slate-900/40 backdrop-blur-xl border border-slate-800/60 rounded-full md:rounded-3xl py-3 px-4 md:p-5 flex md:flex-col items-center md:items-start justify-between transition-all hover:bg-slate-800/40 cursor-pointer">
                    <div className="flex items-center gap-2 mb-0 md:mb-2">
                        <span className="w-2 h-2 rounded-full bg-slate-500"></span>
                        <span className="text-sm font-semibold text-slate-300">Queued</span>
                    </div>
                    <span className="text-lg md:text-3xl font-bold text-white">{queueAnim}</span>
                </div>
            </div>
        </section>
    )
}
