import { useState, useEffect, useRef } from 'react'
import { ItemCardGrid } from '@/components/ItemCardGrid'
import { ItemDetailDrawer } from '@/components/ItemDetailDrawer'
import { UploadZone } from '@/components/UploadZone'
import { InstallPrompt } from '@/components/InstallPrompt'
import { createListing, fetchJobDetails, type JobDetails, type ItemDraft, clearCompleted, clearFailed, deleteJob } from '@/lib/api'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ScannerListener } from '@/components/ScannerListener'
import { ScannerModal } from '@/components/ScannerModal'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useQueryClient } from '@tanstack/react-query'
import { BatchSummaryDialog } from '@/components/BatchSummaryDialog'

export function Dashboard() {
    const queryClient = useQueryClient()

    // Store State
    const jobs = useCommanderStore(state => state.jobs)
    const setJobs = useCommanderStore(state => state.setJobs)
    const selectedJob = useCommanderStore(state => state.selectedJob)
    const setSelectedJob = useCommanderStore(state => state.setSelectedJob)
    const queueStats = useCommanderStore(state => state.queueStats)
    const isProcessing = useCommanderStore(state => state.isProcessing)
    const ebayStatus = useCommanderStore(state => state.ebayStatus)
    const isScanning = useCommanderStore(state => state.isScanning)
    const jobLogs = useCommanderStore(state => state.jobLogs)
    const batchSummary = useCommanderStore(state => state.batchSummary)
    const setBatchSummary = useCommanderStore(state => state.setBatchSummary)

    // Store Actions
    const handleStart = useCommanderStore(state => state.handleStart)
    const handlePause = useCommanderStore(state => state.handlePause)
    const handleScan = useCommanderStore(state => state.handleScan)

    // Keep a ref to latest jobs for use in closures
    const jobsRef = useRef(jobs)
    useEffect(() => { jobsRef.current = jobs }, [jobs])

    // Local UI State
    const [isScannerOpen, setIsScannerOpen] = useState(false)
    const [draft, setDraft] = useState<ItemDraft>({
        title: '',
        price: '29.99',
        condition: '',
        shipping: null,
        scheduledTime: '',
        itemSpecifics: {},
        categoryId: '',
        categoryName: ''
    })

    const updateDraft = (updates: Partial<ItemDraft>) => {
        setDraft(prev => ({ ...prev, ...updates }))
    }
    const [isCreating, setIsCreating] = useState(false)
    const [createResult, setCreateResult] = useState<{ success: boolean; message: string } | null>(null)
    const [jobImages, setJobImages] = useState<Array<{ name: string; url: string }>>([])
    const [jobDetails, setJobDetails] = useState<JobDetails | null>(null)
    const [isLoadingDetails, setIsLoadingDetails] = useState(false)

    // Bulk Selection State
    const [selectedJobIds, setSelectedJobIds] = useState<Set<string>>(new Set())

    const toggleJobSelection = (id: string) => {
        const newSet = new Set(selectedJobIds)
        if (newSet.has(id)) {
            newSet.delete(id)
        } else {
            newSet.add(id)
        }
        setSelectedJobIds(newSet)
    }

    const clearSelection = () => setSelectedJobIds(new Set())

    const handleBulkDelete = async () => {
        if (!confirm(`Delete ${selectedJobIds.size} items?`)) return
        const idsToDelete = new Set(selectedJobIds)
        try {
            const res = await fetch('/api/jobs/bulk-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jobIds: Array.from(idsToDelete) })
            })
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            // Optimistically remove deleted jobs from state
            setJobs(jobs.filter(j => !idsToDelete.has(j.id)))
            if (selectedJob && idsToDelete.has(selectedJob.id)) {
                setSelectedJob(null)
            }
            clearSelection()
        } catch (e) {
            console.error(e)
            alert("Failed to delete jobs")
        }
    }

    // Confirmation dialog state
    const [confirmDialog, setConfirmDialog] = useState<{
        type: 'clear-completed' | 'clear-failed' | 'delete-single' | null
        jobId?: string
        jobName?: string
    }>({ type: null })

    const failedCount = jobs.filter(j => j.status === 'failed').length
    const completedCount = jobs.filter(j => j.status === 'completed').length

    const handleClearCompleted = () => {
        setConfirmDialog({ type: 'clear-completed' })
    }

    const handleClearFailed = () => {
        setConfirmDialog({ type: 'clear-failed' })
    }

    const handleDeleteSingleJob = (jobId: string) => {
        const job = jobs.find(j => j.id === jobId)
        setConfirmDialog({
            type: 'delete-single',
            jobId,
            jobName: job?.display_name || job?.name || jobId
        })
    }

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
            }
        } catch (e) {
            console.error(e)
            alert(`Failed to ${type === 'clear-completed' ? 'clear completed' : type === 'clear-failed' ? 'clear failed' : 'delete'} jobs`)
        }
    }

    // Fetch all images when job is selected
    useEffect(() => {
        if (selectedJob) {
            setJobImages([])
            fetch(`/api/job/${selectedJob.id}/images`)
                .then(res => res.json())
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
                        price: details.suggested_price ? String(details.suggested_price) : '29.99',
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
                    updateDraft(newDraft)
                })
                .catch(err => console.error("Failed to load job details", err))
                .finally(() => setIsLoadingDetails(false))
        } else {
            setJobDetails(null)
            setDraft({
                title: '',
                price: '29.99',
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
    const handleScannerInput = (_bookData: unknown) => {
        // Scanner input handled by ScannerListener component
    }

    const hasItems = jobs.length > 0

    return (
        <div className="flex-1 flex flex-col h-full overflow-hidden relative">
            <ScannerListener onScan={handleScannerInput} />

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                    {/* Header: Mobile/Desktop layout */}
                    <header className="mb-6">
                        <div className="flex justify-between items-start">
                            <div>
                                <h1 className="font-display font-bold text-2xl sm:text-3xl text-stone-800">Workspace</h1>
                                <p className="text-stone-400 text-sm">
                                    {queueStats.total > 0
                                        ? `${queueStats.total} items \u00B7 ${queueStats.pending} pending`
                                        : 'Drop photos to get started'}
                                </p>
                            </div>
                            <div className="flex items-center gap-2">
                                <InstallPrompt />
                            </div>
                        </div>
                        <div className="flex items-center gap-2 mt-3 flex-wrap">
                            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${ebayStatus === 'connected'
                                ? 'bg-blue-50 text-blue-700 border-blue-200'
                                : 'bg-red-50 text-red-700 border-red-200'
                                }`}>
                                <div className={`w-1.5 h-1.5 rounded-full ${ebayStatus === 'connected' ? 'bg-blue-500' : 'bg-red-500'}`} />
                                {ebayStatus === 'connected' ? 'eBay Linked' : 'eBay Offline'}
                            </div>
                            <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-full shadow-sm border border-stone-100">
                                <div className={`w-2 h-2 rounded-full ${isProcessing ? 'bg-green-500 animate-pulse' : 'bg-stone-300'}`} />
                                <span className="text-xs font-medium text-stone-600">
                                    {isProcessing ? 'Active' : 'Ready'}
                                </span>
                            </div>
                        </div>
                    </header>

                    {/* Upload Zone */}
                    <div className="hidden md:block mb-6">
                        <UploadZone
                            compact={hasItems}
                            onUploadComplete={(jobId) => {
                                // Immediately refresh jobs list (belt-and-suspenders with Socket.IO)
                                queryClient.invalidateQueries({ queryKey: ['jobs'] })
                                let attempts = 0
                                const maxAttempts = 20
                                const trySelect = () => {
                                    const found = jobsRef.current.find(j => j.id === jobId)
                                    if (found) {
                                        setSelectedJob(found)
                                    } else if (attempts < maxAttempts) {
                                        attempts++
                                        setTimeout(trySelect, 300)
                                    }
                                }
                                trySelect()
                            }}
                        />
                    </div>

                    {/* Item Card Grid */}
                    <ItemCardGrid
                        jobs={jobs}
                        selectedJob={selectedJob}
                        onSelectJob={(job) => setSelectedJob(job)}
                        isProcessing={isProcessing}
                        onStart={handleStart}
                        onPause={handlePause}
                        onScan={handleScan}
                        isScanning={isScanning}
                        selectedJobIds={selectedJobIds}
                        onToggleSelect={toggleJobSelection}
                        onClearSelection={clearSelection}
                        onBulkDelete={handleBulkDelete}
                        onClearCompleted={handleClearCompleted}
                        onClearFailed={handleClearFailed}
                        onDeleteJob={handleDeleteSingleJob}
                    />
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

            {/* Batch Summary */}
            <BatchSummaryDialog
                open={!!batchSummary}
                onOpenChange={(open) => !open && setBatchSummary(null)}
                summary={batchSummary}
            />
        </div>
    )
}
