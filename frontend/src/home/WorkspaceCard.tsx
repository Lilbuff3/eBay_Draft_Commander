import { useState } from 'react'
import { type Job } from '@/lib/api'
import { getStatusStyle } from '@/lib/status'

/**
 * Workspace item card — uses the REAL product photo.
 *
 * Photo source priority:
 *   1. job.thumbnail_url               (already on the Job object)
 *   2. /api/job/{id}/image/{thumbnail_name}
 *   3. neutral placeholder            (no image yet / still uploading)
 *
 * Status pill is driven by the existing three-bucket model in lib/status.ts
 * (working = persimmon, live = sage, needs_you = red) so it always matches the
 * rest of the app.
 */
export function WorkspaceCard({ job, onSelect }: { job: Job; onSelect: (job: Job) => void }) {
    const style = getStatusStyle(job.status)
    const Icon = style.icon
    // Old jobs can reference an image file that's since been deleted (404).
    // Fall back to the neutral placeholder instead of a broken-image icon.
    const [imgError, setImgError] = useState(false)

    const photo =
        job.thumbnail_url ||
        (job.thumbnail_name ? `/api/job/${job.id}/image/${job.thumbnail_name}` : null)

    const working = style.bucket === 'working'

    return (
        <button
            onClick={() => onSelect(job)}
            className="group text-left bg-white border border-ink-900/[0.07] rounded-2xl overflow-hidden
                       shadow-[0_1px_2px_rgba(34,28,22,0.03)] transition
                       hover:-translate-y-0.5 hover:shadow-[0_12px_24px_-16px_rgba(34,28,22,0.32)]"
        >
            <div className="relative h-32 bg-stone-100">
                {photo && !imgError ? (
                    <img src={photo} alt="" className="w-full h-full object-cover" loading="lazy"
                        onError={() => setImgError(true)} />
                ) : (
                    <div className="w-full h-full grid place-items-center text-stone-400 text-xs font-medium">
                        No photo yet
                    </div>
                )}
                <span className={`absolute top-2 right-2 flex items-center gap-1.5 text-[10.5px] font-semibold
                                  px-2 py-1 rounded-md shadow-sm ${style.bg} ${style.text}`}>
                    <Icon className={`w-3 h-3 ${style.spin ? 'animate-spin' : ''}`} strokeWidth={2.2} />
                    {style.label}
                </span>
            </div>

            <div className="px-3 pt-3 pb-3">
                <div className="text-[13px] font-semibold leading-snug text-ink-800 line-clamp-2 min-h-[34px]">
                    {job.display_name || job.name}
                </div>

                {working ? (
                    <div className="mt-2.5">
                        <div className="flex justify-between text-[11px] font-semibold text-clay-600 mb-1.5">
                            <span>Analyzing…</span>
                        </div>
                        {/* indeterminate bar — the backend status is coarse, so this is a working indicator, not a true % */}
                        <div className="h-1.5 rounded bg-stone-100 overflow-hidden">
                            <div className="h-full w-1/3 rounded bg-gradient-to-r from-persimmon-400 to-clay-400 animate-pulse" />
                        </div>
                    </div>
                ) : (
                    <div className="flex items-center justify-between mt-2">
                        <span className="text-[11.5px] text-stone-400 font-medium">
                            {style.bucket === 'live' && job.listing_id ? `Listed · ${job.listing_id}` :
                                style.bucket === 'needs_you' ? (job.error_type || 'Needs attention') : 'Ready'}
                        </span>
                        {job.price && (
                            <span className="font-display font-bold text-[15px] tracking-[-0.02em] text-ink-800">
                                ${job.price}
                            </span>
                        )}
                    </div>
                )}
            </div>
        </button>
    )
}
