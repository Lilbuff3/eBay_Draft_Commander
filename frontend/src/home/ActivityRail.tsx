import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { fetchJobs } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'
import { useCommanderStore } from '@/store/useCommanderStore'
import { buildActivityFeed, TONE_DOT } from './activityFeed'

/**
 * "Commander · Live" rail — dark glassmorphic integrated card.
 *  - Top: the job currently in `processing` (if any), with a working indicator.
 *  - Below: a timeline of recent real job transitions.
 */
export function ActivityRail() {
    // Socket.IO pushes job updates when connected — only poll as a fallback
    const isSocketConnected = useCommanderStore(s => s.isSocketConnected)
    const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs, refetchInterval: isSocketConnected ? false : 5000 })

    const processing = jobs.find(j => getStatusBucket(j.status) === 'working')
    const feed = buildActivityFeed(jobs)
    const processedToday = jobs.filter(j => getStatusBucket(j.status) === 'live').length

    return (
        <div className="flex flex-col gap-3.5">
            {/* Live Processing Card */}
            <div className="bg-slate-900/40 backdrop-blur-2xl border border-white/5 shadow-glass rounded-3xl p-4">
                <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-[11px] font-bold tracking-wide text-slate-300">COMMANDER · LIVE</span>
                    <span className="ml-auto text-[10px] font-semibold text-slate-500 tracking-wide">
                        {processing ? 'PROCESSING' : 'IDLE'}
                    </span>
                </div>

                {processing ? (
                    <div className="mt-3 p-3 rounded-2xl bg-slate-950/40 border border-white/5">
                        <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-xl grid place-items-center bg-brand-500/20 flex-shrink-0">
                                <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
                            </div>
                            <div className="min-w-0">
                                <div className="text-[12.5px] font-semibold text-white truncate">
                                    {processing.display_name || processing.name}
                                </div>
                                <div className="text-[11px] text-slate-400">Analyzing photos…</div>
                            </div>
                        </div>
                        <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden mt-2.5">
                            <div className="h-full w-1/3 rounded-full bg-gradient-to-r from-brand-400 to-brand-600 animate-pulse shadow-glow" />
                        </div>
                    </div>
                ) : (
                    <div className="mt-3 p-3 rounded-2xl bg-slate-950/40 border border-white/5 text-[12px] text-slate-400">
                        Nothing processing — upload photos to start a batch.
                    </div>
                )}
            </div>

            {/* Timeline Activity Card */}
            <div className="bg-slate-900/40 backdrop-blur-2xl border border-white/5 shadow-glass rounded-3xl px-1.5 pt-1 pb-2">
                <div className="flex items-center justify-between px-3 pt-2.5 pb-2">
                    <span className="text-[11px] font-bold tracking-wide text-slate-400">ACTIVITY</span>
                </div>
                <div className="max-h-[330px] overflow-y-auto px-1.5">
                    {feed.length === 0 && (
                        <div className="px-2 py-6 text-center text-[12px] text-slate-500">No recent activity</div>
                    )}
                    {feed.map(row => (
                        <div key={row.id} className="flex gap-3 px-2 py-2 rounded-xl hover:bg-slate-800/30">
                            <div className="flex flex-col items-center flex-shrink-0 pt-1">
                                <span className={`w-2 h-2 rounded-full ring-[3px] ${TONE_DOT[row.tone]} ${row.tone === 'sage' ? 'ring-emerald-500/20' : row.tone === 'persimmon' ? 'ring-red-500/20' : 'ring-slate-700/50'}`} />
                                <span className="w-px flex-1 bg-slate-800 mt-1" />
                            </div>
                            <div className="min-w-0 pb-0.5">
                                <div className="text-[12.5px] font-medium leading-snug text-slate-300">{row.text}</div>
                                <div className="font-mono text-[10px] text-slate-500 mt-0.5">{row.time}</div>
                            </div>
                        </div>
                    ))}
                </div>
                <div className="flex items-center justify-between px-3 pt-2.5 pb-1.5 mt-1 border-t border-white/5">
                    <span className="text-[11.5px] text-slate-400 font-medium">{processedToday} live</span>
                </div>
            </div>
        </div>
    )
}
