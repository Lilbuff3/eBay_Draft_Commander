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
            className="group text-left bg-slate-900/40 backdrop-blur-2xl border border-white/5 shadow-glass hover:shadow-glass-hover rounded-3xl p-3.5 flex gap-4 items-center transition-colors w-full"
        >
            {/* Thumbnail */}
            <div className="w-20 h-20 rounded-2xl bg-slate-800 overflow-hidden shrink-0 relative">
                {photo && !imgError ? (
                    <img src={photo} alt="" className="w-full h-full object-cover" loading="lazy"
                        onError={() => setImgError(true)} />
                ) : (
                    <div className="w-full h-full grid place-items-center text-slate-500 text-[10px] font-medium">
                        No photo
                    </div>
                )}
                {/* Status indicator on top of image */}
                <span className={`absolute top-1 right-1 flex items-center justify-center w-5 h-5 rounded-full shadow-sm ${style.bucket === 'needs_you' ? 'bg-red-500/80 text-white' : 'bg-brand-500/80 text-white'}`}>
                    <Icon className={`w-3 h-3 ${style.spin ? 'animate-spin' : ''}`} strokeWidth={2.5} />
                </span>
            </div>

            {/* Details */}
            <div className="flex-1 min-w-0">
                <div className="text-[14px] font-bold text-white leading-tight truncate">
                    {job.display_name || job.name}
                </div>
                
                {working ? (
                    <div className="mt-2.5">
                        <div className="flex justify-between text-[11px] font-semibold text-brand-300 mb-1.5">
                            <span>Analyzing…</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                            <div className="h-full w-1/3 rounded-full bg-gradient-to-r from-brand-400 to-brand-600 animate-pulse shadow-glow" />
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col gap-1.5 mt-1">
                        <div className="flex items-center justify-between">
                            <span className="text-[11px] text-slate-400 font-medium truncate pr-2">
                                {style.bucket === 'live' && job.listing_id ? `Listed · ${job.listing_id}` :
                                    style.bucket === 'needs_you' ? (job.error_type || 'Needs attention') : 'Ready'}
                            </span>
                        </div>
                        
                        <div className="flex items-center gap-3">
                            <span className="font-display font-bold text-[18px] tracking-[-0.02em] text-brand-400">
                                {job.price ? `$${job.price}` : '---'}
                            </span>
                            <span className="text-[10px] font-medium bg-slate-800/80 text-slate-300 px-2 py-1 rounded-md border border-slate-700/50">
                                {style.label}
                            </span>
                        </div>
                    </div>
                )}
            </div>
        </motion.button>
    )
}
