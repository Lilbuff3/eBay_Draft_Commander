import { useEffect, useRef } from 'react'
import { ItemDetailDrawer } from '@/components/ItemDetailDrawer'
import { ScannerListener } from '@/components/ScannerListener'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useQueryClient } from '@tanstack/react-query'
import { BatchSummaryDialog } from '@/components/BatchSummaryDialog'
import { DashboardHome } from '@/home/DashboardHome'
import { useItemDraft } from '@/hooks/useItemDraft'

export function Dashboard() {
    const queryClient = useQueryClient()

    // Store State
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

    // Watch for mobile uploads and auto-select
    useEffect(() => {
        if (lastUploadedJobId) {
            queryClient.invalidateQueries({ queryKey: ['jobs'] })
            let attempts = 0
            const maxAttempts = 20
            const trySelect = () => {
                const found = jobsRef.current.find(j => j.id === lastUploadedJobId)
                if (found) {
                    setSelectedJob(found)
                    setLastUploadedJobId(null)
                } else if (attempts < maxAttempts) {
                    attempts++
                    setTimeout(trySelect, 300)
                }
            }
            trySelect()
        }
    }, [lastUploadedJobId, setLastUploadedJobId, setSelectedJob, queryClient])

    return (
        <div className="flex-1 flex flex-col h-full overflow-hidden relative">
            {/* Hardware barcode scanner: listens globally for rapid keystrokes */}
            <ScannerListener onScan={() => { }} />

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                    <DashboardHome userName="Adam" />
                </div>
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
