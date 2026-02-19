import { useState, useEffect } from 'react'
import { ItemCardGrid } from '@/components/ItemCardGrid'
import { ItemDetailDrawer } from '@/components/ItemDetailDrawer'
import { UploadZone } from '@/components/UploadZone'
import { InstallPrompt } from '@/components/InstallPrompt'
import { createListing, type Job, type QueueStats, fetchJobDetails, type JobDetails } from '@/lib/api'
import { ScannerListener } from '@/components/ScannerListener'
import { type LogEntry } from '@/components/LogViewer'
import { ScannerModal } from '@/components/ScannerModal'

interface DashboardProps {
    jobs: Job[]
    selectedJob: Job | null
    setSelectedJob: (job: Job | null) => void
    queueStats: QueueStats
    isProcessing: boolean
    ebayStatus: 'connected' | 'disconnected' | 'checking'
    handleStart: () => void
    handlePause: () => void
    handleScan: () => void
    isScanning: boolean
    scanMessage: string | null
    jobLogs: Record<string, LogEntry[]>
}

export function Dashboard(props: DashboardProps) {
    const { selectedJob, jobs, setSelectedJob, queueStats, isProcessing, ebayStatus, handleScan, isScanning } = props

    // Local UI State
    const [isScannerOpen, setIsScannerOpen] = useState(false)
    const [selectedShipping, setSelectedShipping] = useState<string | null>(null)
    const [listingPrice, setListingPrice] = useState<string>('29.99')
    const [listingTitle, setListingTitle] = useState<string>('')
    const [selectedCondition, setSelectedCondition] = useState<string>('')
    const [scheduledTime, setScheduledTime] = useState<string>('')
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
        try {
            await fetch('/api/jobs/bulk-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jobIds: Array.from(selectedJobIds) })
            })
            clearSelection()
        } catch (e) {
            console.error(e)
            alert("Failed to delete jobs")
        }
    }

    // Fetch all images when job is selected (for ImageGallery)
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
                    setJobDetails(details)
                    setListingTitle(details.user_title || details.ai_title || selectedJob.name)
                    if (details.suggested_price) {
                        setListingPrice(String(details.suggested_price))
                    }
                    if (details.condition) {
                        setSelectedCondition(String(details.condition))
                    }
                })
                .catch(err => console.error("Failed to load job details", err))
                .finally(() => setIsLoadingDetails(false))
        } else {
            setJobDetails(null)
            setListingTitle('')
            setSelectedCondition('')
            setScheduledTime('')
        }
    }, [selectedJob])

    const handleCreateListing = async () => {
        if (!selectedJob) return
        setIsCreating(true)
        setCreateResult(null)

        try {
            const result = await createListing({
                jobId: selectedJob.id,
                price: listingPrice,
                title: listingTitle,
                condition: selectedCondition || undefined,
                fulfillmentPolicy: selectedShipping || undefined,
                scheduledTime: scheduledTime || undefined
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
                    <header className="flex justify-between items-center mb-6">
                        <div>
                            <h1 className="font-display font-bold text-2xl sm:text-3xl text-stone-800">Workspace</h1>
                            <p className="text-stone-400 text-sm">
                                {queueStats.total > 0
                                    ? `${queueStats.total} items \u00B7 ${queueStats.pending} pending`
                                    : 'Drop photos to get started'}
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            <InstallPrompt />
                            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${
                                ebayStatus === 'connected'
                                    ? 'bg-blue-50 text-blue-700 border-blue-200'
                                    : 'bg-red-50 text-red-700 border-red-200'
                            }`}>
                                <div className={`w-1.5 h-1.5 rounded-full ${
                                    ebayStatus === 'connected' ? 'bg-blue-500' : 'bg-red-500'
                                }`} />
                                {ebayStatus === 'connected' ? 'eBay Linked' : 'eBay Offline'}
                            </div>
                            <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-full shadow-sm border border-stone-100">
                                <div className={`w-2 h-2 rounded-full ${
                                    isProcessing ? 'bg-green-500 animate-pulse' : 'bg-stone-300'
                                }`} />
                                <span className="text-xs font-medium text-stone-600">
                                    {isProcessing ? 'Active' : 'Ready'}
                                </span>
                            </div>
                        </div>
                    </header>

                    {/* Upload Zone — expanded when empty, compact when items exist */}
                    <div className="mb-6">
                        <UploadZone
                            compact={hasItems}
                            onUploadComplete={(jobId) => {
                                // Auto-select the newly created job once it appears via Socket.IO
                                const trySelect = () => {
                                    const found = jobs.find(j => j.id === jobId)
                                    if (found) {
                                        setSelectedJob(found)
                                    } else {
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
                        onStart={props.handleStart}
                        onScan={handleScan}
                        isScanning={isScanning}
                        selectedJobIds={selectedJobIds}
                        onToggleSelect={toggleJobSelection}
                        onClearSelection={clearSelection}
                        onBulkDelete={handleBulkDelete}
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
                listingTitle={listingTitle}
                setListingTitle={setListingTitle}
                listingPrice={listingPrice}
                setListingPrice={setListingPrice}
                selectedCondition={selectedCondition}
                setSelectedCondition={setSelectedCondition}
                selectedShipping={selectedShipping}
                setSelectedShipping={setSelectedShipping}
                scheduledTime={scheduledTime}
                setScheduledTime={setScheduledTime}
                isCreating={isCreating}
                onCreateListing={handleCreateListing}
                createResult={createResult}
                logs={selectedJob ? (props.jobLogs[selectedJob.id] || []) : []}
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
