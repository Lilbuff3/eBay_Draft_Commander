import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { fetchJobs } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'
import { buildActivityFeed, TONE_DOT, TONE_HALO } from './activityFeed'

/**
 * "Commander · Live" rail — light, integrated card.
 *  - Top: the job currently in `processing` (if any), with a working indicator.
 *  - Below: a timeline of recent real job transitions (see activityFeed.ts).
 */
export function ActivityRail() {
    const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs, refetchInterval: 4000 })

    const processing = jobs.find(j => getStatusBucket(j.status) === 'working')
    const feed = buildActivityFeed(jobs)
    const processedToday = jobs.filter(j => getStatusBucket(j.status) === 'live').length

    return (
        <div className="flex flex-col gap-3.5">
            <div className="bg-white border border-ink-900/[0.07] rounded-2xl p-4 shadow-[0_1px_2px_rgba(34,28,22,0.03)]">
                <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-sage-500 animate-pulse" />
                    <span className="text-[11px] font-bold tracking-wide text-ink-700">COMMANDER · LIVE</span>
                    <span className="ml-auto text-[10px] font-semibold text-stone-400 tracking-wide">
                        {processing ? 'PROCESSING' : 'IDLE'}
                    </span>
                </div>

                {processing ? (
                    <div className="mt-3 p-3 rounded-xl bg-paper border border-ink-900/[0.05]">
                        <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-lg grid place-items-center bg-clay-300/30 flex-shrink-0">
                                <Loader2 className="w-4 h-4 text-clay-600 animate-spin" />
                            </div>
                            <div className="min-w-0">
                                <div className="text-[12.5px] font-semibold text-ink-800 truncate">
                                    {processing.display_name || processing.name}
                                </div>
                                <div className="text-[11px] text-stone-500">Analyzing photos…</div>
                            </div>
                        </div>
                        <div className="h-1.5 rounded bg-stone-100 overflow-hidden mt-2.5">
                            <div className="h-full w-1/3 rounded bg-gradient-to-r from-persimmon-500 to-clay-400 animate-pulse" />
                        </div>
                    </div>
                ) : (
                    <div className="mt-3 p-3 rounded-xl bg-paper border border-ink-900/[0.05] text-[12px] text-stone-500">
                        Nothing processing — drop photos to start a batch.
                    </div>
                )}
            </div>

            <div className="bg-white border border-ink-900/[0.07] rounded-2xl px-1 pt-1 pb-2 shadow-[0_1px_2px_rgba(34,28,22,0.03)]">
                <div className="flex items-center justify-between px-3 pt-2.5 pb-2">
                    <span className="text-[11px] font-bold tracking-wide text-stone-400">ACTIVITY</span>
                </div>
                <div className="max-h-[330px] overflow-y-auto px-1.5">
                    {feed.length === 0 && (
                        <div className="px-2 py-6 text-center text-[12px] text-stone-400">No recent activity</div>
                    )}
                    {feed.map(row => (
                        <div key={row.id} className="flex gap-3 px-2 py-2 rounded-lg hover:bg-paper">
                            <div className="flex flex-col items-center flex-shrink-0 pt-1">
                                <span className={`w-2 h-2 rounded-full ring-[3px] ${TONE_DOT[row.tone]} ${TONE_HALO[row.tone]}`} />
                                <span className="w-px flex-1 bg-stone-200 mt-1" />
                            </div>
                            <div className="min-w-0 pb-0.5">
                                <div className="text-[12.5px] font-medium leading-snug text-ink-700">{row.text}</div>
                                <div className="font-mono text-[10px] text-stone-400 mt-0.5">{row.time}</div>
                            </div>
                        </div>
                    ))}
                </div>
                <div className="flex items-center justify-between px-3 pt-2.5 pb-1.5 mt-1 border-t border-stone-100">
                    <span className="text-[11.5px] text-stone-400 font-medium">{processedToday} live</span>
                </div>
            </div>
        </div>
    )
}
