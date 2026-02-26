import { type MouseEvent } from 'react'
import { Clock, Loader2, Check, AlertCircle, Image, ChevronRight, CalendarClock, DollarSign, Square, CheckSquare } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Job, JobStatus } from '@/lib/api'

interface CompactItemRowProps {
    job: Job
    isSelected: boolean
    isSelectionMode: boolean
    onToggleSelect: (id: string) => void
    onClick: () => void
}

const statusConfig: Record<JobStatus, { icon: typeof Clock; label: string; color: string; bg: string }> = {
    pending: { icon: Clock, label: 'Pending', color: 'text-stone-500', bg: 'bg-stone-100' },
    processing: { icon: Loader2, label: 'Processing', color: 'text-amber-700', bg: 'bg-amber-50' },
    completed: { icon: Check, label: 'Done', color: 'text-sage-700', bg: 'bg-sage-50' },
    failed: { icon: AlertCircle, label: 'Failed', color: 'text-red-600', bg: 'bg-red-50' },
    paused: { icon: Clock, label: 'Paused', color: 'text-amber-600', bg: 'bg-amber-50' },
    skipped: { icon: Clock, label: 'Skipped', color: 'text-stone-400', bg: 'bg-stone-50' },
    scheduled: { icon: CalendarClock, label: 'Scheduled', color: 'text-blue-600', bg: 'bg-blue-50' },
    needs_review: { icon: AlertCircle, label: 'Review', color: 'text-amber-600', bg: 'bg-amber-50' },
}

export function CompactItemRow({ job, isSelected, isSelectionMode, onToggleSelect, onClick }: CompactItemRowProps) {
    const status = statusConfig[job.status] || statusConfig.pending
    const StatusIcon = status.icon
    const isProcessing = job.status === 'processing'

    const handleClick = (e: MouseEvent) => {
        if (isSelectionMode) {
            e.stopPropagation()
            onToggleSelect(job.id)
        } else {
            onClick()
        }
    }

    const handleLongPress = (e: MouseEvent) => {
        e.preventDefault()
        if (!isSelectionMode) {
            onToggleSelect(job.id)
        }
    }

    const subtitle = job.condition
        ? job.error_type
            ? `${job.condition} · ${job.error_type}`
            : job.condition
        : job.error_type || (
            job.status === 'completed' ? 'Draft ready'
                : job.status === 'processing' ? 'Analyzing...'
                    : job.status === 'failed' ? 'Needs attention'
                        : 'Pending'
        )

    return (
        <button
            type="button"
            onClick={handleClick}
            onContextMenu={handleLongPress}
            className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors',
                'active:bg-stone-100 border-b border-stone-100 last:border-b-0',
                isSelected && !isSelectionMode && 'bg-sage-50/60',
                isSelectionMode && isSelected && 'bg-blue-50/60',
            )}
        >
            {/* Selection checkbox */}
            {isSelectionMode && (
                <div className="flex-shrink-0" onClick={(e) => { e.stopPropagation(); onToggleSelect(job.id) }}>
                    {isSelected ? (
                        <CheckSquare size={20} className="text-blue-600" />
                    ) : (
                        <Square size={20} className="text-stone-300" />
                    )}
                </div>
            )}

            {/* Thumbnail */}
            <div className="w-12 h-12 rounded-lg bg-stone-100 flex-shrink-0 overflow-hidden">
                {job.thumbnail_url ? (
                    <img
                        src={job.thumbnail_url}
                        alt=""
                        className="w-full h-full object-cover"
                        loading="lazy"
                    />
                ) : (
                    <div className="w-full h-full flex items-center justify-center text-stone-300">
                        <Image size={20} />
                    </div>
                )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-medium text-stone-800 truncate">
                        {job.name}
                    </h4>
                    {/* Status pill */}
                    <span className={cn(
                        'flex-shrink-0 inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-md',
                        status.bg, status.color,
                    )}>
                        <StatusIcon size={10} className={isProcessing ? 'animate-spin' : ''} />
                        {status.label}
                    </span>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                    <p className="text-xs text-stone-400 truncate flex-1">
                        {subtitle}
                    </p>
                    {job.price && (
                        <span className="text-xs font-semibold text-green-700 flex items-center flex-shrink-0">
                            <DollarSign size={10} className="mr-0.5" />
                            {job.price}
                        </span>
                    )}
                </div>
            </div>

            {/* Chevron */}
            {!isSelectionMode && (
                <ChevronRight size={16} className="text-stone-300 flex-shrink-0" />
            )}
        </button>
    )
}
