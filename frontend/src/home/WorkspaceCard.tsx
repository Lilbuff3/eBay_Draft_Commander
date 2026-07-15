import { useState } from 'react'
import { motion } from 'framer-motion'
import { type Job } from '@/lib/api'
import { getStatusStyle } from '@/lib/status'

/**
 * Purple Mockup Workspace item card
 */
export function WorkspaceCard({ job, onSelect }: { job: Job; onSelect: (job: Job) => void }) {
    const style = getStatusStyle(job.status)
    const Icon = style.icon
    const [imgError, setImgError] = useState(false)

    const photo =
        job.thumbnail_url ||
        (job.thumbnail_name ? `/api/job/${job.id}/image/${job.thumbnail_name}` : null)

    const working = style.bucket === 'working'

    return (
        <motion.button
            whileHover={{ scale: 1.02, y: -2 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onSelect(job)}
            className="group text-left bg-paper-card border border-stone-200 shadow-sm hover:shadow-md rounded-3xl p-3.5 flex gap-4 items-center transition-shadow w-full"
        >
            {/* Thumbnail */}
            <div className="w-20 h-20 rounded-2xl bg-stone-100 overflow-hidden shrink-0 relative">
                {photo && !imgError ? (
                    <img src={photo} alt="" className="w-full h-full object-cover" loading="lazy"
                        onError={() => setImgError(true)} />
                ) : (
                    <div className="w-full h-full grid place-items-center text-stone-400 text-xs font-medium">
                        No photo
                    </div>
                )}
                {/* Status indicator on top of image */}
                <span className={`absolute top-1 right-1 flex items-center justify-center w-5 h-5 rounded-full shadow-sm ${style.bucket === 'needs_you' ? 'bg-red-500 text-white' : 'bg-persimmon-600 text-white'}`}>
                    <Icon className={`w-3 h-3 ${style.spin ? 'animate-spin' : ''}`} strokeWidth={2.5} />
                </span>
            </div>

            {/* Details */}
            <div className="flex-1 min-w-0">
                <div className="text-sm font-bold text-ink-800 leading-tight truncate">
                    {job.display_name || job.name}
                </div>

                {working ? (
                    <div className="mt-2.5">
                        <div className="flex justify-between text-xs font-semibold text-persimmon-600 mb-1.5">
                            <span>Analyzing…</span>
                        </div>
                        {/* Indeterminate: no per-job progress exists to bind. */}
                        <div className="h-1.5 rounded-full bg-stone-200 overflow-hidden">
                            <div className="h-full w-1/4 rounded-full bg-persimmon-500 progress-indeterminate" />
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col gap-1.5 mt-1">
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-stone-500 font-medium truncate pr-2">
                                {style.bucket === 'live' && job.listing_id ? `Listed · ${job.listing_id}` :
                                    style.bucket === 'needs_you' ? (job.error_type || 'Needs attention') : 'Ready'}
                            </span>
                        </div>

                        <div className="flex items-center gap-3">
                            <span className="font-display font-bold text-[18px] tracking-[-0.02em] text-persimmon-600">
                                {job.price ? `$${job.price}` : '---'}
                            </span>
                            <span className="text-xs font-medium bg-stone-100 text-stone-600 px-2 py-1 rounded-md border border-stone-200">
                                {style.label}
                            </span>
                        </div>
                    </div>
                )}
            </div>
        </motion.button>
    )
}
