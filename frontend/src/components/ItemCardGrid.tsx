import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { Play, Search, Package, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ItemCard } from '@/components/ItemCard'
import type { Job } from '@/lib/api'

type FilterTab = 'all' | 'pending' | 'completed' | 'failed'

interface ItemCardGridProps {
    jobs: Job[]
    selectedJob: Job | null
    onSelectJob: (job: Job) => void
    isProcessing: boolean
    onStart: () => void
    onScan: () => void
    isScanning: boolean
    // Bulk selection
    selectedJobIds: Set<string>
    onToggleSelect: (id: string) => void
    onClearSelection: () => void
    onBulkDelete: () => void
}

export function ItemCardGrid({
    jobs,
    selectedJob,
    onSelectJob,
    isProcessing,
    onStart,
    onScan,
    isScanning,
    selectedJobIds,
    onToggleSelect,
    onClearSelection,
    onBulkDelete,
}: ItemCardGridProps) {
    const [activeFilter, setActiveFilter] = useState<FilterTab>('all')
    const isSelectionMode = selectedJobIds.size > 0

    // Filter jobs by status tab
    const filteredJobs = jobs.filter(job => {
        if (activeFilter === 'all') return true
        if (activeFilter === 'pending') return job.status === 'pending' || job.status === 'processing' || job.status === 'scheduled'
        if (activeFilter === 'completed') return job.status === 'completed'
        if (activeFilter === 'failed') return job.status === 'failed'
        return true
    })

    // Counts for tabs
    const counts = {
        all: jobs.length,
        pending: jobs.filter(j => j.status === 'pending' || j.status === 'processing' || j.status === 'scheduled').length,
        completed: jobs.filter(j => j.status === 'completed').length,
        failed: jobs.filter(j => j.status === 'failed').length,
    }

    const tabs: { key: FilterTab; label: string; count: number }[] = [
        { key: 'all', label: 'All', count: counts.all },
        { key: 'pending', label: 'Pending', count: counts.pending },
        { key: 'completed', label: 'Done', count: counts.completed },
        { key: 'failed', label: 'Failed', count: counts.failed },
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
                            {counts.pending > 0 && (
                                <Button
                                    size="sm"
                                    onClick={onStart}
                                    disabled={isProcessing}
                                    className="text-xs h-8 bg-gradient-to-r from-sage-600 to-sage-700 hover:from-sage-700 hover:to-sage-800 text-white"
                                >
                                    <Play size={14} className="mr-1" />
                                    {isProcessing ? 'Processing...' : 'Process All'}
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
