import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { Play, Pause, Search, Package, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ItemCard } from '@/components/ItemCard'
import type { Job } from '@/lib/api'

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
}: ItemCardGridProps) {
    const [activeFilter, setActiveFilter] = useState<FilterTab>('all')
    const isSelectionMode = selectedJobIds.size > 0

    // Filter jobs by status tab
    const filteredJobs = jobs.filter(job => {
        if (activeFilter === 'all') return true
        if (activeFilter === 'inbox') return job.status === 'pending' || job.status === 'scheduled'
        if (activeFilter === 'processing') return job.status === 'processing'
        if (activeFilter === 'history') return job.status === 'completed'
        if (activeFilter === 'action') return job.status === 'failed' || job.status === 'needs_review'
        return true
    })

    // Counts for tabs
    const counts = {
        all: jobs.length,
        inbox: jobs.filter(j => j.status === 'pending' || j.status === 'scheduled').length,
        processing: jobs.filter(j => j.status === 'processing').length,
        history: jobs.filter(j => j.status === 'completed').length,
        action: jobs.filter(j => j.status === 'failed' || j.status === 'needs_review').length,
    }

    const tabs: { key: FilterTab; label: string; count: number }[] = [
        { key: 'all', label: 'All', count: counts.all },
        { key: 'inbox', label: 'Inbox', count: counts.inbox },
        { key: 'processing', label: 'Processing', count: counts.processing },
        { key: 'action', label: 'Action Needed', count: counts.action },
        { key: 'history', label: 'History', count: counts.history },
    ]

    return (
        <div>
            {/* Toolbar: Filter tabs + Actions */}
            <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
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
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={onClearSelection}
                                className="text-xs h-8"
                            >
                                Cancel
                            </Button>
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={onBulkDelete}
                                className="text-xs h-8"
                            >
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

            {/* Card Grid */}
            {filteredJobs.length > 0 ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
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
