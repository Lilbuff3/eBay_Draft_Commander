import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { fetchJobs } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'
import { useCommanderStore } from '@/store/useCommanderStore'
import { buildActivityFeed, TONE_DOT, TONE_HALO } from './activityFeed'

/**
 * "Commander · Live" rail.
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
            <div className="bg-paper-card border border-stone-200 shadow-sm rounded-3xl p-4">
                <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-sage-500 animate-pulse" />
                    <span className="text-xs font-bold tracking-wide text-stone-600">COMMANDER · LIVE</span>
                    <span className="ml-auto text-xs font-semibold text-stone-500 tracking-wide">
                        {processing ? 'PROCESSING' : 'IDLE'}
                    </span>
                </div>

                {processing ? (
                    <div className="mt-3 p-3 rounded-2xl bg-stone-50 border border-stone-200">
                        <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-xl grid place-items-center bg-persimmon-50 flex-shrink-0">
                                <Loader2 className="w-4 h-4 text-persimmon-600 animate-spin" />
                            </div>
                            <div className="min-w-0">
                                <div className="text-sm font-semibold text-ink-800 truncate">
                                    {processing.display_name || processing.name}
                                </div>
                                <div className="text-xs text-stone-500">Analyzing photos…</div>
                            </div>
                        </div>
                        {/* Indeterminate: no per-job progress exists to bind. */}
                        <div className="h-1.5 rounded-full bg-stone-200 overflow-hidden mt-2.5">
                            <div className="h-full w-1/4 rounded-full bg-persimmon-500 progress-indeterminate" />
                        </div>
                    </div>
                ) : (
                    <div className="mt-3 p-3 rounded-2xl bg-stone-50 border border-stone-200 text-sm text-stone-500">
                        Nothing processing — upload photos to start a batch.
                    </div>
                )}
            </div>

            {/* Timeline Activity Card */}
            <div className="bg-paper-card border border-stone-200 shadow-sm rounded-3xl px-1.5 pt-1 pb-2">
                <div className="flex items-center justify-between px-3 pt-2.5 pb-2">
                    <span className="text-xs font-bold tracking-wide text-stone-500">ACTIVITY</span>
                </div>
                <div className="max-h-[330px] overflow-y-auto px-1.5">
                    {feed.length === 0 && (
                        <div className="px-2 py-6 text-center text-sm text-stone-400">No recent activity</div>
                    )}
                    {feed.map(row => (
                        <div key={row.id} className="flex gap-3 px-2 py-2 rounded-xl hover:bg-stone-100">
                            <div className="flex flex-col items-center flex-shrink-0 pt-1">
                                <span className={`w-2 h-2 rounded-full ring-[3px] ${TONE_DOT[row.tone]} ${TONE_HALO[row.tone]}`} />
                                <span className="w-px flex-1 bg-stone-200 mt-1" />
                            </div>
                            <div className="min-w-0 pb-0.5">
                                <div className="text-sm font-medium leading-snug text-stone-700">{row.text}</div>
                                <div className="font-mono text-xs text-stone-500 mt-0.5">{row.time}</div>
                            </div>
                        </div>
                    ))}
                </div>
                <div className="flex items-center justify-between px-3 pt-2.5 pb-1.5 mt-1 border-t border-stone-200">
                    <span className="text-xs text-stone-500 font-medium">{processedToday} live</span>
                </div>
            </div>
        </div>
    )
}
