import { useState, useRef, useEffect, useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Play, Pause, Search, Package, Trash2, MoreVertical } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ItemCard } from '@/components/ItemCard'
import { CompactItemRow } from '@/components/CompactItemRow'
import { cn } from '@/lib/utils'
import type { Job } from '@/lib/api'
import { useHaptics } from '@/hooks/useHaptics'
import { useCommanderStore } from '@/store/useCommanderStore'

type FilterTab = 'all' | 'inbox' | 'processing' | 'action' | 'history'

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

    // Filter jobs by status tab
    const filteredJobs = useMemo(() => jobs.filter(job => {
        if (activeFilter === 'all') return true
        if (activeFilter === 'inbox') return job.status === 'pending' || job.status === 'processing' || job.status === 'scheduled'
        if (activeFilter === 'history') return job.status === 'completed'
        if (activeFilter === 'action') return job.status === 'failed' || job.status === 'needs_review'
        return true
    }), [jobs, activeFilter])

    // Counts for tabs
    const counts = useMemo(() => ({
        all: jobs.length,
        inbox: jobs.filter(j => j.status === 'pending' || j.status === 'processing' || j.status === 'scheduled').length,
        history: jobs.filter(j => j.status === 'completed').length,
        action: jobs.filter(j => j.status === 'failed' || j.status === 'needs_review').length,
    }), [jobs])

    const tabs: { key: FilterTab; label: string; mobileLabel: string; count: number }[] = [
        { key: 'all', label: 'All', mobileLabel: 'All', count: counts.all },
        { key: 'inbox', label: 'Queue', mobileLabel: 'Queue', count: counts.inbox },
        { key: 'action', label: 'Failed', mobileLabel: 'Failed', count: counts.action },
        { key: 'history', label: 'Listed', mobileLabel: 'Listed', count: counts.history },
    ]

    const overflowActions = [
        { label: isScanning ? 'Scanning...' : 'Scan Inbox', icon: Search, onClick: onScan, disabled: isScanning },
        ...(isProcessing
            ? [{ label: 'Pause Queue', icon: Pause, onClick: onPause, disabled: false }]
            : counts.inbox > 0
                ? [{ label: 'Process All', icon: Play, onClick: onStart, disabled: false }]
                : []
        ),
        ...(counts.action > 0 && onClearFailed
            ? [{ label: 'Clear Failed', icon: Trash2, onClick: onClearFailed, disabled: false, destructive: true }]
            : []
        ),
        ...(counts.history > 0 && onClearCompleted
            ? [{ label: 'Clear Done', icon: Trash2, onClick: onClearCompleted, disabled: false }]
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
                'bg-stone-50',
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
                                            'flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-semibold transition-all whitespace-nowrap',
                                            activeFilter === tab.key
                                                ? 'bg-stone-800 text-white shadow-sm'
                                                : 'bg-white text-stone-500 border border-stone-200 active:bg-stone-100'
                                        )}
                                    >
                                        {tab.mobileLabel}
                                        {tab.count > 0 && (
                                            <span className={cn(
                                                'ml-1',
                                                activeFilter === tab.key ? 'text-stone-300' : 'text-stone-400'
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
                <div className="flex gap-1 p-1 bg-stone-100 rounded-xl">
                    {tabs.map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveFilter(tab.key)}
                            className={`
                                px-3 py-1.5 rounded-lg text-xs font-semibold transition-all
                                ${activeFilter === tab.key
                                    ? 'bg-white shadow-sm text-stone-800'
                                    : 'text-stone-400 hover:text-stone-600'
                                }
                            `}
                        >
                            {tab.label}
                            {tab.count > 0 && (
                                <span className={`ml-1.5 ${activeFilter === tab.key ? 'text-stone-500' : 'text-stone-300'}`}>
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
                                {isScanning ? 'Scanning...' : 'Scan Inbox'}
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
                                counts.inbox > 0 && (
                                    <Button
                                        size="sm"
                                        onClick={onStart}
                                        className="text-xs h-8 bg-gradient-to-r from-sage-600 to-sage-700 hover:from-sage-700 hover:to-sage-800 text-white"
                                    >
                                        <Play size={14} className="mr-1" />
                                        Process All
                                    </Button>
                                )
                            )}
                            {counts.action > 0 && onClearFailed && (
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
                            {counts.history > 0 && onClearCompleted && (
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
                    {/* Mobile: Compact list with enter/exit animations */}
                    <div className="md:hidden bg-white rounded-xl border border-stone-200 overflow-hidden mt-2">
                        <AnimatePresence initial={false}>
                            {filteredJobs.map((job, index) => (
                                <motion.div
                                    layout="position"
                                    key={job.id}
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0, transition: { duration: 0.2 } }}
                                    transition={{
                                        opacity: { duration: 0.2, delay: index < 10 ? index * 0.03 : 0 },
                                        height: { duration: 0.25 },
                                    }}
                                >
                                    <CompactItemRow
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
