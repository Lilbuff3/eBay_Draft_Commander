import { useState, useRef, type MouseEvent, type TouchEvent } from 'react'
import { useHaptics } from '@/hooks/useHaptics'
import { Clock, Loader2, Check, AlertCircle, Image, ChevronRight, CalendarClock, DollarSign, Square, CheckSquare, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Job, JobStatus } from '@/lib/api'

interface CompactItemRowProps {
    job: Job
    isSelected: boolean
    isSelectionMode: boolean
    onToggleSelect: (id: string) => void
    onClick: () => void
    onDelete?: (id: string) => void
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
    pending_review: { icon: AlertCircle, label: 'Review', color: 'text-amber-600', bg: 'bg-amber-50' },
    awaiting_condition: { icon: AlertCircle, label: 'Set Condition', color: 'text-orange-600', bg: 'bg-orange-50' },
};

const SWIPE_THRESHOLD = 80

export function CompactItemRow({ job, isSelected, isSelectionMode, onToggleSelect, onClick, onDelete }: CompactItemRowProps) {
    const { tap, warning } = useHaptics()
    const status = statusConfig[job.status] || statusConfig.pending
    const StatusIcon = status.icon
    const isProcessing = job.status === 'processing'

    // Image state
    const [imgLoaded, setImgLoaded] = useState(false)
    const [imgError, setImgError] = useState(false)

    // Swipe state
    const [swipeX, setSwipeX] = useState(0)
    const [isSwiping, setIsSwiping] = useState(false)
    const [showDelete, setShowDelete] = useState(false)
    const touchStartRef = useRef({ x: 0, y: 0, time: 0 })
    const rowRef = useRef<HTMLDivElement>(null)
    const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    const handleClick = (e: MouseEvent) => {
        if (showDelete) {
            // Tapping on the row when delete is revealed should close it
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

    // Touch handlers for swipe-to-delete and long-press
    const handleTouchStart = (e: TouchEvent) => {
        if (isSelectionMode) return
        const touch = e.touches[0]
        touchStartRef.current = { x: touch.clientX, y: touch.clientY, time: Date.now() }
        setIsSwiping(false)

        // Start long-press timer (500ms)
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

        // Cancel long-press on any significant movement
        if (longPressTimerRef.current && (Math.abs(dx) > 10 || Math.abs(dy) > 10)) {
            clearTimeout(longPressTimerRef.current)
            longPressTimerRef.current = null
        }

        // Only allow left swipe, require more horizontal than vertical movement
        if (!isSwiping && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            setIsSwiping(true)
        }

        if (isSwiping) {
            // Clamp: allow left swipe up to -120px, slight right spring back
            const clampedX = showDelete
                ? Math.min(0, Math.max(-120, dx - SWIPE_THRESHOLD))
                : Math.min(10, Math.max(-120, dx))
            setSwipeX(clampedX)
        }
    }

    const handleTouchEnd = () => {
        // Cancel any pending long-press
        if (longPressTimerRef.current) {
            clearTimeout(longPressTimerRef.current)
            longPressTimerRef.current = null
        }

        if (!isSwiping) return
        setIsSwiping(false)

        if (swipeX < -SWIPE_THRESHOLD) {
            // Commit: lock at delete position
            tap()
            setSwipeX(-SWIPE_THRESHOLD)
            setShowDelete(true)
        } else {
            // Snap back
            setSwipeX(0)
            setShowDelete(false)
        }
    }

    const handleDeleteClick = () => {
        warning()
        if (onDelete) {
            onDelete(job.id)
        }
        setSwipeX(0)
        setShowDelete(false)
    }

    const displayName = job.display_name || job.name

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
        <div className="relative overflow-hidden" ref={rowRef}>
            {/* Delete action behind the row */}
            {onDelete && (
                <div className="absolute inset-y-0 right-0 flex items-center">
                    <button
                        onClick={handleDeleteClick}
                        aria-label="Delete item"
                        className="h-full px-6 bg-red-500 text-white flex items-center gap-1.5 text-sm font-medium active:bg-red-600 transition-colors w-20"
                    >
                        <Trash2 size={16} />
                        Delete
                    </button>
                </div>
            )}

            {/* Swipeable content */}
            <div
                className={cn(
                    'will-change-transform',
                    !isSwiping && 'transition-transform duration-[250ms] ease-out'
                )}
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
                        'w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors bg-white',
                        'active:bg-stone-100 border-b border-stone-100 last:border-b-0',
                        isSelected && !isSelectionMode && 'bg-sage-50/60',
                        isSelectionMode && isSelected && 'bg-blue-50/60',
                    )}
                >
                    {/* Selection checkbox */}
                    {isSelectionMode && (
                        <div className="flex-shrink-0" aria-label={isSelected ? 'Deselect item' : 'Select item'} role="checkbox" aria-checked={isSelected ? 'true' : 'false'} onClick={(e) => { e.stopPropagation(); onToggleSelect(job.id) }}>
                            {isSelected ? (
                                <CheckSquare size={20} className="text-blue-600" />
                            ) : (
                                <Square size={20} className="text-stone-300" />
                            )}
                        </div>
                    )}

                    {/* Thumbnail */}
                    <div className={cn("w-12 h-12 rounded-lg bg-stone-100 flex-shrink-0 overflow-hidden", !imgLoaded && job.thumbnail_url && !imgError && "animate-pulse")}>
                        {job.thumbnail_url && !imgError ? (
                            <img
                                src={job.thumbnail_url}
                                alt=""
                                className={cn("w-full h-full object-cover transition-opacity duration-200", imgLoaded ? "opacity-100" : "opacity-0")}
                                loading="lazy"
                                onLoad={() => setImgLoaded(true)}
                                onError={() => setImgError(true)}
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
                                {displayName}
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
            </div>
        </div>
    )
}
