import { useState, useRef, useEffect, useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Play, Pause, Search, Package, Trash2, MoreVertical } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ItemCard } from '@/components/ItemCard'
import { ItemPhotoCard } from '@/components/ItemPhotoCard'
import { cn } from '@/lib/utils'
import type { Job } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'
import { useHaptics } from '@/hooks/useHaptics'
import { useCommanderStore } from '@/store/useCommanderStore'

type FilterTab = 'all' | 'working' | 'live' | 'needs_you'
const FILTER_BUCKETS = ['working', 'live', 'needs_you'] as const

interface ItemCardGridProps {
    jobs: Job[]
    selectedJob: Job | null
    onSelectJob: (job: Job) => void
    isProcessing: boolean
    onStart: () => void
    onPause: () => void
    onScan: () => void
    isScanning: boolean
    // Bulk selection
    selectedJobIds: Set<string>
    onToggleSelect: (id: string) => void
    onClearSelection: () => void
    onBulkDelete: () => void
    onClearFailed?: () => void
    onClearCompleted?: () => void
    onPurgeStale?: () => void
    onDeleteJob?: (id: string) => void
}

export function ItemCardGrid({
    jobs,
    selectedJob,
    onSelectJob,
    isProcessing,
    onStart,
    onPause,
    onScan,
    isScanning,
    selectedJobIds,
    onToggleSelect,
    onClearSelection,
    onBulkDelete,
    onClearFailed,
    onClearCompleted,
    onPurgeStale,
    onDeleteJob,
}: ItemCardGridProps) {
    const activeFilter = useCommanderStore(state => state.activeFilter) as FilterTab
    const setActiveFilter = useCommanderStore(state => state.setActiveFilter)
    const [showOverflow, setShowOverflow] = useState(false)
    const [isScrolled, setIsScrolled] = useState(false)
    const overflowRef = useRef<HTMLDivElement>(null)
    const { tap } = useHaptics()
    const isSelectionMode = selectedJobIds.size > 0

    // Track scroll position for sticky header shadow
    useEffect(() => {
        const handleScroll = () => {
            setIsScrolled(window.scrollY > 10)
        }
        window.addEventListener('scroll', handleScroll, { passive: true })
        return () => window.removeEventListener('scroll', handleScroll)
    }, [])

    // Close overflow menu on outside click
    useEffect(() => {
        if (!showOverflow) return
        const handleClick = (e: MouseEvent) => {
            if (overflowRef.current && !overflowRef.current.contains(e.target as Node)) {
                setShowOverflow(false)
            }
        }
        document.addEventListener('click', handleClick)
        return () => document.removeEventListener('click', handleClick)
    }, [showOverflow])

    // Filter jobs by the 3-state bucket (unknown/legacy filter -> show all)
    const filteredJobs = useMemo(() => jobs.filter(job => {
        if (!FILTER_BUCKETS.includes(activeFilter as typeof FILTER_BUCKETS[number])) return true
        return getStatusBucket(job.status) === activeFilter
    }), [jobs, activeFilter])

    // Counts for tabs
    const counts = useMemo(() => ({
        all: jobs.length,
        working: jobs.filter(j => getStatusBucket(j.status) === 'working').length,
        live: jobs.filter(j => getStatusBucket(j.status) === 'live').length,
        needs_you: jobs.filter(j => getStatusBucket(j.status) === 'needs_you').length,
    }), [jobs])

    const tabs: { key: FilterTab; label: string; mobileLabel: string; count: number }[] = [
        { key: 'all', label: 'All', mobileLabel: 'All', count: counts.all },
        { key: 'working', label: 'Working', mobileLabel: 'Working', count: counts.working },
        { key: 'live', label: 'Live', mobileLabel: 'Live', count: counts.live },
        { key: 'needs_you', label: 'Needs you', mobileLabel: 'Needs', count: counts.needs_you },
    ]

    const overflowActions = [
        { label: isScanning ? 'Scanning…' : 'Scan Inbox', icon: Search, onClick: onScan, disabled: isScanning },
        ...(isProcessing
            ? [{ label: 'Pause Queue', icon: Pause, onClick: onPause, disabled: false }]
            : counts.working > 0
                ? [{ label: 'Process All', icon: Play, onClick: onStart, disabled: false }]
                : []
        ),
        ...(counts.needs_you > 0 && onClearFailed
            ? [{ label: 'Clear Failed', icon: Trash2, onClick: onClearFailed, disabled: false, destructive: true }]
            : []
        ),
        ...(counts.live > 0 && onClearCompleted
            ? [{ label: 'Clear Done', icon: Trash2, onClick: onClearCompleted, disabled: false }]
            : []
        ),
        ...(onPurgeStale
            ? [{ label: 'Clear Stale', icon: Trash2, onClick: onPurgeStale, disabled: false }]
            : []
        ),
    ]

    return (
        <div>
            {/* ═══════════════════════════════════════════════
                MOBILE: Sticky filter bar + overflow menu
                ═══════════════════════════════════════════════ */}
            <div className={cn(
                'md:hidden sticky top-0 z-30 -mx-4 px-4 pt-2 pb-2 transition-shadow',
                'bg-paper/95 backdrop-blur-sm',
                isScrolled && 'shadow-sm',
            )}>
                {/* Selection mode bar */}
                {isSelectionMode ? (
                    <div className="flex items-center justify-between py-1">
                        <span className="text-sm font-medium text-stone-600">
                            {selectedJobIds.size} selected
                        </span>
                        <div className="flex items-center gap-2">
                            <Button variant="outline" size="sm" onClick={onClearSelection} className="text-xs h-8">
                                Cancel
                            </Button>
                            <Button variant="destructive" size="sm" onClick={onBulkDelete} className="text-xs h-8">
                                <Trash2 size={14} className="mr-1" />
                                Delete
                            </Button>
                        </div>
                    </div>
                ) : (
                    /* Filter chips — horizontal scroll */
                    <div className="flex items-center gap-2">
                        <div className="flex-1 overflow-x-auto scrollbar-hide">
                            <div className="flex gap-1.5 pb-0.5">
                                {tabs.map(tab => (
                                    <button
                                        key={tab.key}
                                        onClick={() => { tap(); setActiveFilter(tab.key) }}
                                        className={cn(
                                            'flex-shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold transition whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500/50',
                                            activeFilter === tab.key
                                                ? 'bg-ink-800 text-paper shadow-sm'
                                                : 'bg-white text-stone-500 border border-stone-200 active:bg-stone-100'
                                        )}
                                    >
                                        {tab.mobileLabel}
                                        {tab.count > 0 && (
                                            <span className={cn(
                                                'ml-1',
                                                activeFilter === tab.key ? 'text-persimmon-400' : 'text-stone-400'
                                            )}>
                                                {tab.count}
                                            </span>
                                        )}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Overflow menu trigger */}
                        <div className="relative flex-shrink-0" ref={overflowRef}>
                            <button
                                onClick={() => { tap(); setShowOverflow(!showOverflow) }}
                                className="p-2 rounded-full bg-white border border-stone-200 text-stone-500 active:bg-stone-100"
                                aria-label="Actions"
                            >
                                <MoreVertical size={16} />
                            </button>

                            {/* Overflow dropdown */}
                            {showOverflow && (
                                <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-xl shadow-lg border border-stone-200 py-1 z-50">
                                    {overflowActions.map((action, i) => (
                                        <button
                                            key={i}
                                            onClick={() => { tap(); action.onClick(); setShowOverflow(false) }}
                                            disabled={action.disabled}
                                            className={cn(
                                                'w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-left transition-colors',
                                                action.disabled ? 'opacity-40' : 'active:bg-stone-50',
                                                'destructive' in action && action.destructive ? 'text-red-600' : 'text-stone-700',
                                            )}
                                        >
                                            <action.icon size={16} className={action.disabled && action.label.includes('Scan') ? 'animate-spin' : ''} />
                                            {action.label}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* ═══════════════════════════════════════════════
                DESKTOP: Original toolbar (unchanged)
                ═══════════════════════════════════════════════ */}
            <div className="hidden md:flex items-center justify-between mb-4 flex-wrap gap-3">
                {/* Filter Tabs */}
                <div className="flex gap-1 p-1 bg-stone-200/50 rounded-xl">
                    {tabs.map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveFilter(tab.key)}
                            className={`
                                px-3.5 py-1.5 rounded-lg text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500/50
                                ${activeFilter === tab.key
                                    ? 'bg-white shadow-sm text-ink-800'
                                    : 'text-stone-500 hover:text-stone-700'
                                }
                            `}
                        >
                            {tab.label}
                            {tab.count > 0 && (
                                <span className={`ml-1.5 ${activeFilter === tab.key ? 'text-persimmon-500' : 'text-stone-400'}`}>
                                    {tab.count}
                                </span>
                            )}
                        </button>
                    ))}
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-2">
                    {isSelectionMode && (
                        <>
                            <span className="text-xs text-stone-500 font-medium">
                                {selectedJobIds.size} selected
                            </span>
                            <Button variant="outline" size="sm" onClick={onClearSelection} className="text-xs h-8">
                                Cancel
                            </Button>
                            <Button variant="destructive" size="sm" onClick={onBulkDelete} className="text-xs h-8">
                                <Trash2 size={14} className="mr-1" />
                                Delete
                            </Button>
                        </>
                    )}

                    {!isSelectionMode && (
                        <>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={onScan}
                                disabled={isScanning}
                                className="text-xs h-8"
                            >
                                <Search size={14} className={`mr-1 ${isScanning ? 'animate-spin' : ''}`} />
                                {isScanning ? 'Scanning…' : 'Scan Inbox'}
                            </Button>
                            {isProcessing ? (
                                <Button
                                    size="sm"
                                    onClick={onPause}
                                    className="text-xs h-8 bg-stone-800 hover:bg-stone-900 text-white"
                                >
                                    <Pause size={14} className="mr-1" />
                                    Pause Queue
                                </Button>
                            ) : (
                                counts.working > 0 && (
                                    <Button
                                        size="sm"
                                        onClick={onStart}
                                        className="text-xs h-8 bg-persimmon-500 hover:bg-persimmon-600 text-white shadow-sm"
                                    >
                                        <Play size={14} className="mr-1" />
                                        Process All
                                    </Button>
                                )
                            )}
                            {counts.needs_you > 0 && onClearFailed && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={onClearFailed}
                                    className="text-xs h-8 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                                >
                                    <Trash2 size={14} className="mr-1" />
                                    Clear Failed
                                </Button>
                            )}
                            {counts.live > 0 && onClearCompleted && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={onClearCompleted}
                                    className="text-xs h-8 text-stone-600 hover:text-stone-700 hover:bg-stone-100 border-stone-200"
                                >
                                    <Trash2 size={14} className="mr-1" />
                                    Clear Done
                                </Button>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* ═══════════════════════════════════════════════
                ITEMS — Compact list on mobile, grid on desktop
                ═══════════════════════════════════════════════ */}
            {filteredJobs.length > 0 ? (
                <>
                    {/* Mobile: single-column photo cards with enter/exit animations */}
                    <div className="md:hidden grid grid-cols-1 gap-3 mt-2">
                        <AnimatePresence initial={false}>
                            {filteredJobs.map((job, index) => (
                                <motion.div
                                    layout="position"
                                    key={job.id}
                                    initial={{ opacity: 0, scale: 0.97 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.97, transition: { duration: 0.2 } }}
                                    transition={{
                                        opacity: { duration: 0.2, delay: index < 10 ? index * 0.03 : 0 },
                                        scale: { duration: 0.2 },
                                    }}
                                >
                                    <ItemPhotoCard
                                        job={job}
                                        isSelected={selectedJob?.id === job.id || selectedJobIds.has(job.id)}
                                        isSelectionMode={isSelectionMode}
                                        onToggleSelect={onToggleSelect}
                                        onClick={() => onSelectJob(job)}
                                        onDelete={onDeleteJob}
                                    />
                                </motion.div>
                            ))}
                        </AnimatePresence>
                    </div>

                    {/* Desktop: Card grid */}
                    <div className="hidden md:grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                        <AnimatePresence mode="popLayout">
                            {filteredJobs.map(job => (
                                <ItemCard
                                    key={job.id}
                                    job={job}
                                    isSelected={selectedJob?.id === job.id || selectedJobIds.has(job.id)}
                                    isSelectionMode={isSelectionMode}
                                    onToggleSelect={onToggleSelect}
                                    onClick={() => onSelectJob(job)}
                                />
                            ))}
                        </AnimatePresence>
                    </div>
                </>
            ) : (
                <div className="text-center py-16 text-stone-400">
                    <Package size={48} className="mx-auto mb-3 opacity-40" />
                    <p className="font-medium text-stone-500">
                        {activeFilter === 'all' ? 'No items yet' : `No ${activeFilter} items`}
                    </p>
                    <p className="text-sm mt-1">
                        {activeFilter === 'all'
                            ? 'Drop photos above or scan your inbox to get started'
                            : 'Try a different filter'}
                    </p>
                </div>
            )}
        </div>
    )
}
