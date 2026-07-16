import { useCallback, useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { ItemDetailDrawer } from '@/components/ItemDetailDrawer'
import { ScannerListener, type ScannedBook } from '@/components/ScannerListener'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useQueryClient } from '@tanstack/react-query'
import { BatchSummaryDialog } from '@/components/BatchSummaryDialog'
import { DashboardHome } from '@/home/DashboardHome'
import { useItemDraft } from '@/hooks/useItemDraft'

export function Dashboard() {
    const queryClient = useQueryClient()

    // Store State
    const setActiveTab = useCommanderStore(state => state.setActiveTab)
    const jobs = useCommanderStore(state => state.jobs)
    const selectedJob = useCommanderStore(state => state.selectedJob)
    const setSelectedJob = useCommanderStore(state => state.setSelectedJob)
    const lastUploadedJobId = useCommanderStore(state => state.lastUploadedJobId)
    const setLastUploadedJobId = useCommanderStore(state => state.setLastUploadedJobId)
    const jobLogs = useCommanderStore(state => state.jobLogs)
    const batchSummary = useCommanderStore(state => state.batchSummary)
    const setBatchSummary = useCommanderStore(state => state.setBatchSummary)

    // Everything about the selected job's listing draft lives in the hook:
    // details/images fetching, user-edit-protected merge, submission.
    const {
        draft, updateDraft,
        jobDetails, isLoadingDetails,
        jobImages, setJobImages,
        isCreating, createResult,
        submitListing,
    } = useItemDraft(selectedJob)

    // Keep a ref to latest jobs for use in closures
    const jobsRef = useRef(jobs)
    useEffect(() => { jobsRef.current = jobs }, [jobs])

    // Mobile upload landed: toast and get out of the way. Auto-opening the edit
    // drawer here killed capture momentum — the whole point is snap → next item,
    // with review happening in a batch later. The Review action looks the job up
    // at tap time so it works whether or not the jobs refetch has landed yet.
    useEffect(() => {
        if (!lastUploadedJobId) return
        const jobId = lastUploadedJobId
        setLastUploadedJobId(null)
        queryClient.invalidateQueries({ queryKey: ['jobs'] })
        toast.success('Item uploaded — AI is building the listing', {
            description: 'Keep snapping; review whenever you like.',
            action: {
                label: 'Review',
                onClick: () => {
                    const found = jobsRef.current.find(j => j.id === jobId)
                    if (found) setSelectedJob(found)
                    else toast.info('Still processing — it will appear in the workspace shortly.')
                },
            },
        })
    }, [lastUploadedJobId, setLastUploadedJobId, setSelectedJob, queryClient])

    // A wedge scan on the home screen queues the book into the Books tab
    // (same localStorage handoff Sourcing's "Send to Books" uses — BatchScan
    // reads 'batchScanItems' on mount).
    const handleWedgeScan = useCallback((book: ScannedBook) => {
        try {
            const saved = localStorage.getItem('batchScanItems')
            const items: unknown[] = saved ? JSON.parse(saved) : []
            let condition = 'USED_GOOD'
            try { condition = localStorage.getItem('batchScanSessionCondition') || 'USED_GOOD' } catch { /* default */ }
            items.unshift({
                id: crypto.randomUUID(),
                isbn: book.isbn,
                title: book.title,
                author: book.item_specifics?.Author || '',
                condition,
                price: book.price?.toString() || '',
                status: 'found',
                stock_photo: book.stock_photo,
                fullData: book,
            })
            localStorage.setItem('batchScanItems', JSON.stringify(items))
            toast.success('Queued in Books tab', {
                description: book.title,
                action: { label: 'Open Books', onClick: () => setActiveTab('batch-scan') },
            })
        } catch {
            toast.error('Could not queue scan — Books list storage full?')
        }
    }, [setActiveTab])

    return (
        <div className="flex-1 flex flex-col h-full overflow-hidden relative">
            {/* Hardware barcode scanner: listens globally for rapid keystrokes */}
            <ScannerListener onScan={handleWedgeScan} />

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto">
                <DashboardHome userName="Adam" />
            </div>

            {/* Detail Drawer */}
            <ItemDetailDrawer
                open={!!selectedJob}
                onClose={() => setSelectedJob(null)}
                job={selectedJob}
                jobDetails={jobDetails}
                isLoadingDetails={isLoadingDetails}
                images={jobImages}
                onReorderImages={setJobImages}
                draft={draft}
                updateDraft={updateDraft}
                isCreating={isCreating}
                onCreateListing={submitListing}
                createResult={createResult}
                logs={selectedJob ? (jobLogs[selectedJob.id] || []) : []}
            />

            {/* Batch Summary */}
            <BatchSummaryDialog
                open={!!batchSummary}
                onOpenChange={(open) => !open && setBatchSummary(null)}
                summary={batchSummary}
            />
        </div>
    )
}
