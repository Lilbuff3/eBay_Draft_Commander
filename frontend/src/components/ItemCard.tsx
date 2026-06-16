import React, { forwardRef, useState, type MouseEvent } from 'react'
import { motion } from 'framer-motion'
import { Loader2, Image, Square, CheckSquare } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getStatusStyle } from '@/lib/status'
import type { Job } from '@/lib/api'

interface ItemCardProps {
    job: Job
    isSelected: boolean
    isSelectionMode: boolean
    onToggleSelect: (id: string) => void
    onClick: () => void
}

const ItemCardInner = forwardRef<HTMLDivElement, ItemCardProps>(function ItemCard(
    { job, isSelected, isSelectionMode, onToggleSelect, onClick },
    ref
) {
    const status = getStatusStyle(job.status)
    const StatusIcon = status.icon
    const isProcessing = job.status === 'processing'

    const handleCardClick = (e: MouseEvent) => {
        if (isSelectionMode) {
            e.stopPropagation()
            onToggleSelect(job.id)
        } else {
            onClick()
        }
    }

    const [imgLoaded, setImgLoaded] = useState(false)
    const [imgError, setImgError] = useState(false)

    const scheduledDate = job.scheduled_time ? new Date(job.scheduled_time) : null
    const isScheduledFuture = scheduledDate && scheduledDate > new Date()

    return (
        <motion.div
            ref={ref}
            layout
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            onClick={handleCardClick}
            role="button"
            tabIndex={0}
            aria-label={job.display_name || job.name}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    if (isSelectionMode) onToggleSelect(job.id)
                    else onClick()
                }
            }}
            className={cn(
                'rounded-2xl cursor-pointer relative group transition overflow-hidden bg-white border',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper',
                isSelected && !isSelectionMode
                    ? 'border-persimmon-400 ring-2 ring-persimmon-500/20 shadow-md'
                    : 'border-stone-200/80 hover:border-stone-300 hover:shadow-[0_8px_24px_-12px_rgba(33,29,24,0.25)] hover:-translate-y-0.5',
                isSelectionMode && isSelected && 'border-persimmon-400 ring-2 ring-persimmon-400/20 bg-persimmon-50/30'
            )}
        >
            {/* Selection Checkbox — top-left overlay */}
            <div
                className={cn(
                    "absolute top-2 left-2 z-10 transition duration-200",
                    isSelectionMode ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                )}
                onClick={(e) => {
                    e.stopPropagation()
                    onToggleSelect(job.id)
                }}
            >
                <div className="bg-white/90 backdrop-blur-sm rounded-lg p-1 shadow-sm">
                    {isSelectionMode && isSelected ? (
                        <CheckSquare size={18} className="text-persimmon-600" />
                    ) : (
                        <Square size={18} className="text-stone-400 hover:text-stone-600" />
                    )}
                </div>
            </div>

            {/* Status pill — top-right overlay */}
            <div className={cn(
                'absolute top-2.5 right-2.5 z-10 flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold shadow-sm',
                status.bg, status.text
            )}>
                <StatusIcon size={12} className={status.spin ? 'animate-spin' : ''} />
                <span>{status.label}</span>
            </div>

            {/* Image */}
            <div className={cn("aspect-[5/4] bg-stone-100 overflow-hidden relative", !imgLoaded && job.thumbnail_url && !imgError && "animate-pulse")}>
                {job.thumbnail_url && !imgError ? (
                    <img
                        src={job.thumbnail_url}
                        alt={job.name}
                        className={cn("w-full h-full object-cover transition duration-300 group-hover:scale-105", imgLoaded ? "opacity-100" : "opacity-0")}
                        onLoad={() => setImgLoaded(true)}
                        onError={() => setImgError(true)}
                    />
                ) : (
                    <div className="w-full h-full flex items-center justify-center text-stone-300">
                        <Image size={40} />
                    </div>
                )}

                {/* Processing overlay */}
                {isProcessing && (
                    <div className="absolute inset-0 bg-ink-900/10 flex items-center justify-center">
                        <div className="bg-white/90 backdrop-blur-sm rounded-full p-3 shadow-lg">
                            <Loader2 size={24} className="text-persimmon-500 animate-spin" />
                        </div>
                    </div>
                )}
            </div>

            {/* Info */}
            <div className="p-3.5">
                <h4 className="font-medium text-ink-800 text-sm line-clamp-2 leading-snug min-h-[2.5em]">
                    {job.display_name || job.name}
                </h4>

                <div className="flex items-center justify-between mt-2.5 gap-2">
                    <div className="flex items-center gap-1.5 flex-wrap min-w-0">
                        {job.condition && (
                            <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-stone-100 text-stone-600 border border-stone-200/80 truncate">
                                {job.condition}
                            </span>
                        )}
                    </div>

                    {job.price && (
                        <span className="font-display font-bold text-[15px] text-ink-800 tabular-nums flex-shrink-0">
                            ${job.price}
                        </span>
                    )}
                </div>

                {/* Subtitle */}
                <p className="text-[11px] text-stone-400 mt-1.5 truncate">
                    {isScheduledFuture
                        ? `Scheduled ${scheduledDate?.toLocaleDateString()}`
                        : job.listing_id
                            ? `Listed: ${job.listing_id}`
                            : job.status === 'completed' ? 'Draft ready'
                                : job.status === 'failed' ? 'Needs attention'
                                    : job.status === 'processing' ? 'Analyzing…'
                                        : 'Pending analysis'}
                </p>

                {/* Error indicator */}
                {job.error_type && (
                    <div className="mt-2 text-[10px] text-red-600 bg-red-50 px-2 py-1 rounded-lg border border-red-100 truncate" title={job.error_message || ''}>
                        {job.error_type}
                    </div>
                )}
            </div>
        </motion.div>
    )
})

export const ItemCard = React.memo(ItemCardInner)
