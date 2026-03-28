import React, { forwardRef, useState, type MouseEvent } from 'react'
import { motion } from 'framer-motion'
import { Clock, Loader2, Check, AlertCircle, Image, Square, CheckSquare, CalendarClock, DollarSign } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import type { Job, JobStatus } from '@/lib/api'

interface ItemCardProps {
    job: Job
    isSelected: boolean
    isSelectionMode: boolean
    onToggleSelect: (id: string) => void
    onClick: () => void
}

const statusConfig: Record<JobStatus, { icon: typeof Clock; color: string; bgColor: string; badgeVariant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
    pending: { icon: Clock, color: 'text-stone-500', bgColor: 'bg-stone-100', badgeVariant: 'secondary' },
    processing: { icon: Loader2, color: 'text-white', bgColor: 'bg-clay-400', badgeVariant: 'default' },
    completed: { icon: Check, color: 'text-sage-700', bgColor: 'bg-sage-100', badgeVariant: 'outline' },
    failed: { icon: AlertCircle, color: 'text-red-600', bgColor: 'bg-red-100', badgeVariant: 'destructive' },
    paused: { icon: Clock, color: 'text-amber-600', bgColor: 'bg-amber-100', badgeVariant: 'secondary' },
    skipped: { icon: Clock, color: 'text-stone-400', bgColor: 'bg-stone-100', badgeVariant: 'outline' },
    scheduled: { icon: CalendarClock, color: 'text-blue-600', bgColor: 'bg-blue-100', badgeVariant: 'secondary' },
    needs_review: { icon: AlertCircle, color: 'text-amber-600', bgColor: 'bg-amber-100', badgeVariant: 'secondary' },
    pending_review: { icon: AlertCircle, color: 'text-amber-600', bgColor: 'bg-amber-100', badgeVariant: 'secondary' },
    awaiting_condition: { icon: AlertCircle, color: 'text-orange-600', bgColor: 'bg-orange-100', badgeVariant: 'secondary' },
};

const ItemCardInner = forwardRef<HTMLDivElement, ItemCardProps>(function ItemCard(
    { job, isSelected, isSelectionMode, onToggleSelect, onClick },
    ref
) {
    const status = statusConfig[job.status] || statusConfig.pending
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
            className={cn(
                'rounded-2xl cursor-pointer relative group transition-all overflow-hidden bg-white border',
                isSelected && !isSelectionMode
                    ? 'border-sage-500 ring-2 ring-sage-500/20 shadow-lg'
                    : 'border-stone-200 hover:border-stone-300 hover:shadow-md hover:translate-y-[-2px]',
                isSelectionMode && isSelected && 'border-blue-400 ring-2 ring-blue-400/20 bg-blue-50/30'
            )}
        >
            {/* Selection Checkbox — top-left overlay */}
            <div
                className={cn(
                    "absolute top-2 left-2 z-10 transition-all duration-200",
                    isSelectionMode ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                )}
                onClick={(e) => {
                    e.stopPropagation()
                    onToggleSelect(job.id)
                }}
            >
                <div className="bg-white/90 backdrop-blur-sm rounded-lg p-1 shadow-sm">
                    {isSelectionMode && isSelected ? (
                        <CheckSquare size={18} className="text-blue-600" />
                    ) : (
                        <Square size={18} className="text-stone-400 hover:text-stone-600" />
                    )}
                </div>
            </div>

            {/* Status Badge — top-right overlay */}
            <div className={cn(
                'absolute top-2 right-2 z-10 flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium',
                status.bgColor, status.color
            )}>
                <StatusIcon size={12} className={isProcessing ? 'animate-spin' : ''} />
                <span className="capitalize">{job.status}</span>
            </div>

            {/* Image */}
            <div className={cn("aspect-[5/4] bg-stone-100 overflow-hidden relative", !imgLoaded && job.thumbnail_url && !imgError && "animate-pulse")}>
                {job.thumbnail_url && !imgError ? (
                    <img
                        src={job.thumbnail_url}
                        alt={job.name}
                        className={cn("w-full h-full object-cover transition-all duration-300 group-hover:scale-105", imgLoaded ? "opacity-100" : "opacity-0")}
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
                    <div className="absolute inset-0 bg-black/10 flex items-center justify-center">
                        <div className="bg-white/90 backdrop-blur-sm rounded-full p-3 shadow-lg">
                            <Loader2 size={24} className="text-clay-500 animate-spin" />
                        </div>
                    </div>
                )}
            </div>

            {/* Info */}
            <div className="p-3">
                <h4 className="font-medium text-stone-800 text-sm line-clamp-2 leading-snug min-h-[2.5em]">
                    {job.display_name || job.name}
                </h4>

                <div className="flex items-center justify-between mt-2">
                    <div className="flex items-center gap-1.5 flex-wrap">
                        {job.condition && (
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-amber-50 text-amber-700 border-amber-200">
                                {job.condition}
                            </Badge>
                        )}
                    </div>

                    {job.price && (
                        <span className="text-sm font-semibold text-green-700 flex items-center">
                            <DollarSign size={12} className="mr-0.5" />
                            {job.price}
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
                                    : job.status === 'processing' ? 'Analyzing...'
                                        : 'Pending analysis'}
                </p>

                {/* Error indicator */}
                {job.error_type && (
                    <div className="mt-2 text-[10px] text-red-500 bg-red-50 px-2 py-1 rounded-lg border border-red-100 truncate" title={job.error_message || ''}>
                        {job.error_type}
                    </div>
                )}
            </div>
        </motion.div>
    )
})

export const ItemCard = React.memo(ItemCardInner)
