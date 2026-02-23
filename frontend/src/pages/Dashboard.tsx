import { useState, useEffect, useRef } from 'react'
import { ItemCardGrid } from '@/components/ItemCardGrid'
import { ItemDetailDrawer } from '@/components/ItemDetailDrawer'
import { UploadZone } from '@/components/UploadZone'
import { InstallPrompt } from '@/components/InstallPrompt'
import { createListing, fetchJobDetails, type JobDetails, type ItemDraft, clearCompleted, clearFailed } from '@/lib/api'
import { ScannerListener } from '@/components/ScannerListener'
import { ScannerModal } from '@/components/ScannerModal'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useJobSync } from '@/hooks/useJobSync'

export function Dashboard() {
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

    // Store Actions
    const handleStart = useCommanderStore(state => state.handleStart)
    const handlePause = useCommanderStore(state => state.handlePause)
    const handleScan = useCommanderStore(state => state.handleScan)

    // Sync Actions
    useJobSync()

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
        itemSpecifics: {}
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

    const handleClearCompleted = async () => {
        try {
            await clearCompleted()
            setJobs(jobs.filter(j => j.status !== 'completed'))
        } catch (e) {
            console.error(e)
            alert("Failed to clear completed jobs")
        }
    }

    const handleClearFailed = async () => {
        try {
            await clearFailed()
            setJobs(jobs.filter(j => j.status !== 'failed'))
        } catch (e) {
            console.error(e)
            alert("Failed to clear failed jobs")
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
                        condition: details.condition ? String(details.condition) : ''
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
                itemSpecifics: {}
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
                fulfillmentPolicy: draft.shipping || undefined,
                scheduledTime: draft.scheduledTime || undefined,
                itemSpecifics: draft.itemSpecifics
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
    const handleScannerInput = (bookData: unknown) => {
        console.log("Book Scanned:", bookData)
    }

    const hasItems = jobs.length > 0

    return (
        <div className="flex-1 flex flex-col h-full overflow-hidden relative">
            <ScannerListener onScan={handleScannerInput} />

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                    {/* Header */}
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
                            <div className="hidden md:block">
                                <InstallPrompt />
                            </div>
                        </div>
                        <div className="flex items-center gap-2 mt-3 flex-wrap">
                            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${ebayStatus === 'connected'
                                ? 'bg-blue-50 text-blue-700 border-blue-200'
                                : 'bg-red-50 text-red-700 border-red-200'
                                }`}>
                                <div className={`w-1.5 h-1.5 rounded-full ${ebayStatus === 'connected' ? 'bg-blue-500' : 'bg-red-500'
                                    }`} />
                                {ebayStatus === 'connected' ? 'eBay Linked' : 'eBay Offline'}
                            </div>
                            <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-full shadow-sm border border-stone-100">
                                <div className={`w-2 h-2 rounded-full ${isProcessing ? 'bg-green-500 animate-pulse' : 'bg-stone-300'
                                    }`} />
                                <span className="text-xs font-medium text-stone-600">
                                    {isProcessing ? 'Active' : 'Ready'}
                                </span>
                            </div>
                        </div>
                    </header>

                    {/* Upload Zone */}
                    <div className="mb-6">
                        <UploadZone
                            compact={hasItems}
                            onUploadComplete={(jobId) => {
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
        </div>
    )
}
