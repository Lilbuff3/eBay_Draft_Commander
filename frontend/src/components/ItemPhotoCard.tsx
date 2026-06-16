import { useState, useRef, type MouseEvent, type TouchEvent } from 'react'
import { useHaptics } from '@/hooks/useHaptics'
import { Loader2, Image, Square, CheckSquare, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getStatusStyle } from '@/lib/status'
import type { Job } from '@/lib/api'

interface ItemPhotoCardProps {
    job: Job
    isSelected: boolean
    isSelectionMode: boolean
    onToggleSelect: (id: string) => void
    onClick: () => void
    onDelete?: (id: string) => void
}

const SWIPE_THRESHOLD = 80

export function ItemPhotoCard({ job, isSelected, isSelectionMode, onToggleSelect, onClick, onDelete }: ItemPhotoCardProps) {
    const { tap, warning } = useHaptics()
    const status = getStatusStyle(job.status)
    const StatusIcon = status.icon
    const isProcessing = job.status === 'processing'

    const [imgLoaded, setImgLoaded] = useState(false)
    const [imgError, setImgError] = useState(false)

    // Swipe state
    const [swipeX, setSwipeX] = useState(0)
    const [isSwiping, setIsSwiping] = useState(false)
    const [showDelete, setShowDelete] = useState(false)
    const touchStartRef = useRef({ x: 0, y: 0, time: 0 })
    const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    const handleClick = (e: MouseEvent) => {
        if (showDelete) {
            setShowDelete(false)
            setSwipeX(0)
            return
        }
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

    const handleTouchStart = (e: TouchEvent) => {
        if (isSelectionMode) return
        const touch = e.touches[0]
        touchStartRef.current = { x: touch.clientX, y: touch.clientY, time: Date.now() }
        setIsSwiping(false)
        longPressTimerRef.current = setTimeout(() => {
            tap()
            if (!isSelectionMode) {
                onToggleSelect(job.id)
            }
            longPressTimerRef.current = null
        }, 500)
    }

    const handleTouchMove = (e: TouchEvent) => {
        if (isSelectionMode) return
        const touch = e.touches[0]
        const dx = touch.clientX - touchStartRef.current.x
        const dy = touch.clientY - touchStartRef.current.y

        if (longPressTimerRef.current && (Math.abs(dx) > 10 || Math.abs(dy) > 10)) {
            clearTimeout(longPressTimerRef.current)
            longPressTimerRef.current = null
        }

        if (!isSwiping && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            setIsSwiping(true)
        }

        if (isSwiping) {
            const clampedX = showDelete
                ? Math.min(0, Math.max(-120, dx - SWIPE_THRESHOLD))
                : Math.min(10, Math.max(-120, dx))
            setSwipeX(clampedX)
        }
    }

    const handleTouchEnd = () => {
        if (longPressTimerRef.current) {
            clearTimeout(longPressTimerRef.current)
            longPressTimerRef.current = null
        }
        if (!isSwiping) return
        setIsSwiping(false)

        if (swipeX < -SWIPE_THRESHOLD) {
            tap()
            setSwipeX(-SWIPE_THRESHOLD)
            setShowDelete(true)
        } else {
            setSwipeX(0)
            setShowDelete(false)
        }
    }

    const handleDeleteClick = () => {
        warning()
        if (onDelete) onDelete(job.id)
        setSwipeX(0)
        setShowDelete(false)
    }

    const displayName = job.display_name || job.name
    const scheduledDate = job.scheduled_time ? new Date(job.scheduled_time) : null
    const isScheduledFuture = scheduledDate && scheduledDate > new Date()

    const subtitle = isScheduledFuture
        ? `Scheduled ${scheduledDate?.toLocaleDateString()}`
        : job.error_type
            ? job.error_type
            : job.status === 'completed' ? 'Draft ready'
                : job.status === 'processing' ? 'Analyzing…'
                    : job.status === 'failed' ? 'Needs attention'
                        : 'Pending analysis'

    return (
        <div className="relative overflow-hidden rounded-2xl">
            {/* Delete action behind the card */}
            {onDelete && (
                <div className="absolute inset-y-0 right-0 flex items-stretch">
                    <button
                        onClick={handleDeleteClick}
                        aria-label="Delete item"
                        className="px-6 bg-red-500 text-white flex flex-col items-center justify-center gap-1 text-xs font-semibold active:bg-red-600 transition-colors w-24"
                    >
                        <Trash2 size={18} />
                        Delete
                    </button>
                </div>
            )}

            {/* Swipeable content */}
            <div
                className={cn('will-change-transform', !isSwiping && 'transition-transform duration-[250ms] ease-out')}
                style={{ transform: `translateX(${swipeX}px)` }}
                onTouchStart={handleTouchStart}
                onTouchMove={handleTouchMove}
                onTouchEnd={handleTouchEnd}
            >
                <button
                    type="button"
                    onClick={handleClick}
                    onContextMenu={handleLongPress}
                    className={cn(
                        'w-full text-left bg-white rounded-2xl border overflow-hidden transition active:scale-[0.99]',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper',
                        isSelected && !isSelectionMode
                            ? 'border-persimmon-400 ring-2 ring-persimmon-500/20'
                            : 'border-stone-200/80',
                        isSelectionMode && isSelected && 'border-persimmon-400 ring-2 ring-persimmon-400/20',
                    )}
                >
                    {/* Image */}
                    <div className={cn("relative aspect-[5/4] bg-stone-100 overflow-hidden", !imgLoaded && job.thumbnail_url && !imgError && "animate-pulse")}>
                        {job.thumbnail_url && !imgError ? (
                            <img
                                src={job.thumbnail_url}
                                alt=""
                                loading="lazy"
                                className={cn("w-full h-full object-cover transition-opacity duration-200", imgLoaded ? "opacity-100" : "opacity-0")}
                                onLoad={() => setImgLoaded(true)}
                                onError={() => setImgError(true)}
                            />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-stone-300">
                                <Image size={40} />
                            </div>
                        )}

                        {/* Status pill */}
                        <span className={cn(
                            'absolute top-2.5 right-2.5 inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold shadow-sm',
                            status.bg, status.text,
                        )}>
                            <StatusIcon size={12} className={status.spin ? 'animate-spin' : ''} />
                            {status.label}
                        </span>

                        {/* Selection checkbox */}
                        {isSelectionMode && (
                            <span
                                className="absolute top-2.5 left-2.5 bg-white/90 backdrop-blur-sm rounded-lg p-1 shadow-sm"
                                role="checkbox"
                                aria-checked={isSelected}
                                aria-label={isSelected ? 'Deselect item' : 'Select item'}
                                onClick={(e) => { e.stopPropagation(); onToggleSelect(job.id) }}
                            >
                                {isSelected
                                    ? <CheckSquare size={18} className="text-persimmon-600" />
                                    : <Square size={18} className="text-stone-400" />}
                            </span>
                        )}

                        {/* Processing overlay */}
                        {isProcessing && (
                            <div className="absolute inset-0 bg-ink-900/10 flex items-center justify-center">
                                <div className="bg-white/90 backdrop-blur-sm rounded-full p-3 shadow-lg">
                                    <Loader2 size={22} className="text-persimmon-500 animate-spin" />
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Info */}
                    <div className="p-3.5">
                        <h4 className="font-medium text-ink-800 text-[15px] line-clamp-2 leading-snug">
                            {displayName}
                        </h4>
                        <div className="flex items-center justify-between mt-2 gap-2">
                            <div className="flex items-center gap-1.5 min-w-0">
                                {job.condition && (
                                    <span className="text-[11px] font-medium px-2 py-0.5 rounded-md bg-stone-100 text-stone-600 border border-stone-200/80 truncate">
                                        {job.condition}
                                    </span>
                                )}
                                {!job.condition && (
                                    <span className="text-[11px] text-stone-400 truncate">{subtitle}</span>
                                )}
                            </div>
                            {job.price && (
                                <span className="font-display font-bold text-[17px] text-ink-800 tabular-nums flex-shrink-0">
                                    ${job.price}
                                </span>
                            )}
                        </div>
                        {job.error_type && (
                            <div className="mt-2 text-[11px] text-red-600 bg-red-50 px-2 py-1 rounded-lg border border-red-100 truncate" title={job.error_message || ''}>
                                {job.error_type}
                            </div>
                        )}
                    </div>
                </button>
            </div>
        </div>
    )
}
