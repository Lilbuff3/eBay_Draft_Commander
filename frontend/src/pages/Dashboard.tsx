import { useState, useEffect, useRef } from 'react'
import { ItemDetailDrawer } from '@/components/ItemDetailDrawer'
import { createListing, fetchJobDetails, fetchJobImages, type JobDetails, type ItemDraft, clearCompleted, clearFailed, deleteJob, bulkDeleteJobs } from '@/lib/api'
import { resolveDraftPrice } from '@/lib/draftPrice'
import { mergeDraft } from '@/lib/mergeDraft'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ScannerListener } from '@/components/ScannerListener'
import { ScannerModal } from '@/components/ScannerModal'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useQueryClient } from '@tanstack/react-query'
import { BatchSummaryDialog } from '@/components/BatchSummaryDialog'
import { DashboardHome } from '@/home/DashboardHome'

export function Dashboard() {
    const queryClient = useQueryClient()

    // Store State
    const jobs = useCommanderStore(state => state.jobs)
    const setJobs = useCommanderStore(state => state.setJobs)
    const selectedJob = useCommanderStore(state => state.selectedJob)
    const setSelectedJob = useCommanderStore(state => state.setSelectedJob)
    const lastUploadedJobId = useCommanderStore(state => state.lastUploadedJobId)
    const setLastUploadedJobId = useCommanderStore(state => state.setLastUploadedJobId)
    const jobLogs = useCommanderStore(state => state.jobLogs)
    const batchSummary = useCommanderStore(state => state.batchSummary)
    const setBatchSummary = useCommanderStore(state => state.setBatchSummary)

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

    // Local UI State
    const [isScannerOpen, setIsScannerOpen] = useState(false)
    const [draft, setDraft] = useState<ItemDraft>({
        title: '',
        price: '',
        condition: '',
        shipping: null,
        scheduledTime: '',
        itemSpecifics: {},
        categoryId: '',
        categoryName: ''
    })

    // Fields the user has edited for the currently selected job. Server
    // refreshes (socket job_update -> details refetch) must not overwrite them.
    const touchedFieldsRef = useRef<Set<string>>(new Set())
    const draftJobIdRef = useRef<string | null>(null)

    const updateDraft = (updates: Partial<ItemDraft>) => {
        Object.keys(updates).forEach(key => touchedFieldsRef.current.add(key))
        setDraft(prev => ({ ...prev, ...updates }))
    }
    const [isCreating, setIsCreating] = useState(false)
    const [createResult, setCreateResult] = useState<{ success: boolean; message: string } | null>(null)
    const [jobImages, setJobImages] = useState<Array<{ name: string; url: string }>>([])
    const [jobDetails, setJobDetails] = useState<JobDetails | null>(null)
    const [isLoadingDetails, setIsLoadingDetails] = useState(false)

    const [selectedJobIds, setSelectedJobIds] = useState<Set<string>>(new Set())
    const clearSelection = () => setSelectedJobIds(new Set())

    // Confirmation dialog state
    const [confirmDialog, setConfirmDialog] = useState<{
        type: 'clear-completed' | 'clear-failed' | 'delete-single' | 'bulk-delete' | null
        jobId?: string
        jobName?: string
    }>({ type: null })

    const failedCount = jobs.filter(j => j.status === 'failed').length
    const completedCount = jobs.filter(j => j.status === 'completed').length

    const executeConfirm = async (deleteFolders: boolean) => {
        const { type, jobId } = confirmDialog
        setConfirmDialog({ type: null })

        try {
            if (type === 'clear-completed') {
                await clearCompleted(deleteFolders)
                setJobs(jobs.filter(j => j.status !== 'completed'))
            } else if (type === 'clear-failed') {
                await clearFailed(deleteFolders)
                setJobs(jobs.filter(j => j.status !== 'failed'))
            } else if (type === 'delete-single' && jobId) {
                await deleteJob(jobId, deleteFolders)
                setJobs(jobs.filter(j => j.id !== jobId))
                if (selectedJob?.id === jobId) setSelectedJob(null)
            } else if (type === 'bulk-delete') {
                const idsToDelete = new Set(selectedJobIds)
                await bulkDeleteJobs(Array.from(idsToDelete), deleteFolders)
                setJobs(jobs.filter(j => !idsToDelete.has(j.id)))
                if (selectedJob && idsToDelete.has(selectedJob.id)) {
                    setSelectedJob(null)
                }
                clearSelection()
            }
        } catch (e) {
            console.error(e)
            toast.error(`Failed to ${type === 'clear-completed' ? 'clear completed' : type === 'clear-failed' ? 'clear failed' : 'delete'} jobs`)
        }
    }

    // Fetch all images when job is selected
    useEffect(() => {
        if (selectedJob) {
            setJobImages([])
            fetchJobImages(selectedJob.id)
                .then(data => {
                    if (data.images && data.images.length > 0) {
                        setJobImages(data.images.map((img: { name: string; url?: string }) => ({
                            name: img.name,
                            url: img.url || `/api/job/${selectedJob.id}/image/${img.name}`
                        })))
                    }
                })
                .catch(err => console.error("Failed to load job images", err))
        } else {
            setJobImages([])
        }
    }, [selectedJob])

    // Fetch job details when job is selected
    useEffect(() => {
        if (selectedJob) {
            if (draftJobIdRef.current !== selectedJob.id) {
                // Different job selected: discard edits and start clean
                draftJobIdRef.current = selectedJob.id
                touchedFieldsRef.current = new Set()
                setDraft({
                    title: '',
                    price: '',
                    condition: '',
                    shipping: null,
                    scheduledTime: '',
                    itemSpecifics: {},
                    categoryId: '',
                    categoryName: ''
                })
            }
            setIsLoadingDetails(true)
            setJobDetails(null)
            fetchJobDetails(selectedJob.id)
                .then(details => {
                    if (!details.success) {
                        console.warn('fetchJobDetails returned success=false', details)
                        return
                    }
                    setJobDetails(details)
                    const newDraft: Partial<ItemDraft> = {
                        title: details.user_title || details.ai_title || selectedJob.name,
                        price: resolveDraftPrice(details),
                        condition: details.condition
                            ? (typeof details.condition === 'object' && details.condition !== null
                                ? String((details.condition as Record<string, unknown>).state ?? (details.condition as Record<string, unknown>).value ?? '')
                                : String(details.condition))
                            : '',
                        categoryId: details.category_id || '',
                        categoryName: details.category_name || ''
                    }

                    if (details.scheduled_time) {
                        const dateObj = new Date(details.scheduled_time);
                        const offset = dateObj.getTimezoneOffset() * 60000;
                        const localISOTime = new Date(dateObj.getTime() - offset).toISOString().slice(0, 16);
                        newDraft.scheduledTime = localISOTime
                    } else {
                        const nextWeek = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
                        const offset = nextWeek.getTimezoneOffset() * 60000;
                        const localISOTime = new Date(nextWeek.getTime() - offset).toISOString().slice(0, 16);
                        newDraft.scheduledTime = localISOTime
                    }
                    if (details.item_specifics) {
                        newDraft.itemSpecifics = { ...details.item_specifics }
                    }
                    // Merge instead of overwrite: job_update socket events
                    // re-run this effect while the user may be mid-edit
                    setDraft(prev => mergeDraft(newDraft, prev, touchedFieldsRef.current))
                })
                .catch(err => console.error("Failed to load job details", err))
                .finally(() => setIsLoadingDetails(false))
        } else {
            setJobDetails(null)
            draftJobIdRef.current = null
            touchedFieldsRef.current = new Set()
            setDraft({
                title: '',
                price: '',
                condition: '',
                shipping: null,
                scheduledTime: '',
                itemSpecifics: {},
                categoryId: '',
                categoryName: ''
            })
        }
    }, [selectedJob])

    const priceIsInvalid = !draft.price || parseFloat(draft.price) <= 0

    const handleCreateListing = async () => {
        if (!selectedJob) return
        if (priceIsInvalid) return
        setIsCreating(true)
        setCreateResult(null)

        try {
            const result = await createListing({
                jobId: selectedJob.id,
                price: draft.price,
                title: draft.title,
                condition: draft.condition || undefined,
                categoryId: draft.categoryId || undefined,
                categoryName: draft.categoryName || undefined,
                fulfillmentPolicy: draft.shipping || undefined,
                scheduledTime: draft.scheduledTime || undefined,
                itemSpecifics: draft.itemSpecifics,
                orderedImages: jobImages.map(img => img.name)
            })

            if (result.success) {
                setCreateResult({ success: true, message: result.message || 'Listing created!' })
            } else {
                setCreateResult({ success: false, message: result.error || 'Failed to create listing' })
            }
        } catch (e) {
            setCreateResult({ success: false, message: 'Error creating listing' })
            console.error(e)
        } finally {
            setIsCreating(false)
        }
    }

    // Handle scanner input
    const handleScannerInput = () => {
        // Scanner input handled by ScannerListener component
    }



    return (
        <div className="flex-1 flex flex-col h-full overflow-hidden relative">
            <ScannerListener onScan={handleScannerInput} />

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
                onCreateListing={handleCreateListing}
                createResult={createResult}
                logs={selectedJob ? (jobLogs[selectedJob.id] || []) : []}
            />

            {/* Scanner Modal */}
            <ScannerModal
                isOpen={isScannerOpen}
                onOpenChange={setIsScannerOpen}
                onJobCreated={() => { }}
            />

            {/* Confirmation Dialogs */}
            <ConfirmDialog
                open={confirmDialog.type === 'clear-failed'}
                onOpenChange={(open) => !open && setConfirmDialog({ type: null })}
                title="Clear Failed Items"
                description="Remove all failed items from the app."
                count={failedCount}
                showFolderOption
                onConfirm={executeConfirm}
                confirmLabel="Clear Failed"
            />
            <ConfirmDialog
                open={confirmDialog.type === 'clear-completed'}
                onOpenChange={(open) => !open && setConfirmDialog({ type: null })}
                title="Clear Completed Items"
                description="Remove all completed items from the app."
                count={completedCount}
                showFolderOption
                onConfirm={executeConfirm}
                confirmLabel="Clear Done"
            />
            <ConfirmDialog
                open={confirmDialog.type === 'delete-single'}
                onOpenChange={(open) => !open && setConfirmDialog({ type: null })}
                title={`Delete "${confirmDialog.jobName || 'item'}"`}
                description="Remove this item from the app."
                showFolderOption
                onConfirm={executeConfirm}
                confirmLabel="Delete"
            />
            <ConfirmDialog
                open={confirmDialog.type === 'bulk-delete'}
                onOpenChange={(open) => !open && setConfirmDialog({ type: null })}
                title={`Delete ${selectedJobIds.size} Items`}
                description={`Remove ${selectedJobIds.size} selected items from the app.`}
                count={selectedJobIds.size}
                showFolderOption
                onConfirm={executeConfirm}
                confirmLabel="Delete All"
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
