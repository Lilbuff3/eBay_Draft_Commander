import { useState, useEffect } from 'react'
import { AnimatePresence } from 'framer-motion'
import { Camera, Search, Image, Upload, CalendarClock } from 'lucide-react'
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StageProgress } from '@/components/StageProgress'
import { WorkflowStage } from '@/lib/stages'
import { QueueCard } from '@/components/QueueCard'
import { ActionBar } from '@/components/ActionBar'
import { ShippingSelector } from '@/components/ShippingSelector'
import { UploadZone } from '@/components/UploadZone'
import { InstallPrompt } from '@/components/InstallPrompt'
import { createListing, type Job, type QueueStats, addFolderToQueue, fetchJobDetails, type JobDetails } from '@/lib/api'
import { ScannerListener } from '@/components/ScannerListener'
import { LogViewer, type LogEntry } from '@/components/LogViewer'
import { BulkActionBar } from '@/components/BulkActionBar'
import { ScannerModal } from '@/components/ScannerModal'
import { Barcode } from 'lucide-react'

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

interface DashboardContentProps extends DashboardProps {
    isMobile: boolean
    listingPrice: string
    setListingPrice: (price: string) => void
    listingTitle: string
    setListingTitle: (title: string) => void
    selectedShipping: string | null
    setSelectedShipping: (id: string | null) => void
    scheduledTime: string
    setScheduledTime: (time: string) => void
    isCreating: boolean
    handleCreateListing: () => void
    createResult: { success: boolean; message: string } | null
    previewImage?: string | null
    scanMessage: string | null
    jobLogs: Record<string, LogEntry[]>
    handleScanBarcode: () => void
    jobDetails: JobDetails | null
    isLoadingDetails: boolean
}

const DashboardContent = ({
    isMobile = false,
    selectedJob,
    listingPrice,
    setListingPrice,
    listingTitle,
    setListingTitle,
    selectedShipping,
    setSelectedShipping,
    scheduledTime,
    setScheduledTime,
    isCreating,
    handleCreateListing,
    createResult,
    handleScan,
    isScanning,
    scanMessage,
    previewImage,
    jobLogs,
    handleScanBarcode,
    jobDetails,
    isLoadingDetails
}: DashboardContentProps) => (
    <div className={`grid ${isMobile ? 'grid-cols-1 flex flex-col' : 'grid-cols-12'} gap-6 mb-24`}>
        {/* Hero Image Section */}
        <div className={`${isMobile ? 'w-full order-1' : 'col-span-12'} glass-panel rounded-3xl p-6 relative group overflow-hidden`}>
            {!selectedJob ? (
                /* Show Upload Zone when no job selected */
                <div className="py-8">
                    <h2 className="text-xl font-semibold text-stone-700 mb-4 text-center">Step 1: Add Photos</h2>
                    <UploadZone onUploadComplete={() => { }} />
                    <div className="flex flex-col items-center gap-4 mt-6">
                        <div className="flex items-center gap-2 w-full max-w-xs">
                            <div className="h-px bg-stone-100 flex-1" />
                            <span className="text-[10px] uppercase font-bold text-stone-300">OR</span>
                            <div className="h-px bg-stone-100 flex-1" />
                        </div>
                        <Button
                            onClick={handleScan}
                            disabled={isScanning}
                            variant="outline"
                            className="w-full max-w-xs h-12 rounded-xl border-dashed border-2 hover:border-blue-400 hover:bg-blue-50/50 transition-all group"
                        >
                            <Search className={`mr-2 group-hover:text-blue-500 ${isScanning ? 'animate-spin' : ''}`} size={18} />
                            {isScanning ? 'Scanning Inbox...' : 'Scan "inbox" Folder'}
                        </Button>
                        <Button
                            onClick={handleScanBarcode}
                            variant="outline"
                            className="w-full max-w-xs h-12 rounded-xl border-dashed border-2 hover:border-purple-400 hover:bg-purple-50/50 transition-all group"
                        >
                            <Barcode className="mr-2 group-hover:text-purple-500" size={18} />
                            Look up via Barcode/ISBN
                        </Button>
                        {scanMessage && (
                            <p className="text-xs font-medium text-blue-600 animate-in fade-in slide-in-from-top-1">
                                {scanMessage}
                            </p>
                        )}
                        <p className="text-center text-stone-400 text-sm">Upload product photos or scan for folders you've prepared</p>
                    </div>
                </div>
            ) : (
                /* Show Image Preview */
                <>
                    <div className="absolute top-4 right-4 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                            className="bg-black/50 hover:bg-black/70 text-white p-2 rounded-lg backdrop-blur-sm"
                            aria-label="Update photo"
                        >
                            <Camera size={18} />
                        </button>
                    </div>

                    <div className="h-64 rounded-2xl bg-stone-100 flex items-center justify-center mb-6 overflow-hidden relative">
                        {previewImage ? (
                            <img
                                src={previewImage}
                                alt={selectedJob.name}
                                className="w-full h-full object-contain"
                            />
                        ) : (
                            <div className="text-stone-300 flex flex-col items-center">
                                <Image size={48} />
                                <span className="text-sm font-medium mt-2">{selectedJob.name}</span>
                                <span className="text-xs mt-1">No images found</span>
                            </div>
                        )}
                    </div>

                    {/* AI Analysis Section */}
                    {isLoadingDetails ? (
                        <div className="flex items-center justify-center py-8">
                            <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
                            <span className="ml-2 text-stone-500">Loading analysis...</span>
                        </div>
                    ) : jobDetails ? (
                        <div className="space-y-4">
                            {/* Title Input */}
                            <div>
                                <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                    Listing Title
                                </label>
                                <Input
                                    placeholder="Item Title..."
                                    value={listingTitle}
                                    onChange={(e) => setListingTitle(e.target.value)}
                                    className="bg-stone-50 font-medium"
                                />
                            </div>

                            {/* Price and Category Row */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                        Price
                                    </label>
                                    <div className="relative">
                                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400">$</span>
                                        <Input
                                            placeholder="0.00"
                                            className="bg-stone-50 pl-7"
                                            value={listingPrice}
                                            onChange={(e) => setListingPrice(e.target.value)}
                                        />
                                    </div>
                                    {jobDetails.pricing_data?.price_source && (
                                        <p className="text-[10px] text-stone-400 mt-1">
                                            {jobDetails.pricing_data.price_source}
                                        </p>
                                    )}
                                </div>
                                <div>
                                    <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                        Category
                                    </label>
                                    <div className="bg-stone-50 rounded-lg px-3 py-2 text-sm text-stone-600 border border-stone-200">
                                        {jobDetails.category_name || jobDetails.category_id || 'Auto-detect'}
                                    </div>
                                </div>
                            </div>

                            {/* Condition */}
                            {jobDetails.condition && (
                                <div>
                                    <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                        Condition
                                    </label>
                                    <Badge variant="secondary" className="bg-amber-100 text-amber-700">
                                        {jobDetails.condition}
                                    </Badge>
                                </div>
                            )}

                            {/* Item Specifics */}
                            {jobDetails.item_specifics && Object.keys(jobDetails.item_specifics).length > 0 && (
                                <div>
                                    <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-2 block">
                                        Item Specifics
                                    </label>
                                    <div className="bg-stone-50 rounded-xl p-3 border border-stone-100">
                                        <div className="grid grid-cols-2 gap-2 text-sm">
                                            {Object.entries(jobDetails.item_specifics).slice(0, 8).map(([key, value]) => (
                                                <div key={key} className="flex gap-1">
                                                    <span className="text-stone-400 font-medium">{key}:</span>
                                                    <span className="text-stone-700 truncate">{String(value)}</span>
                                                </div>
                                            ))}
                                        </div>
                                        {Object.keys(jobDetails.item_specifics).length > 8 && (
                                            <p className="text-[10px] text-stone-400 mt-2">+{Object.keys(jobDetails.item_specifics).length - 8} more</p>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Description Preview */}
                            {jobDetails.ai_description && (
                                <div>
                                    <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-2 block">
                                        Description Preview
                                    </label>
                                    <div className="bg-stone-50 rounded-xl p-3 border border-stone-100 max-h-32 overflow-y-auto">
                                        <div
                                            className="text-sm text-stone-600 prose prose-sm max-w-none"
                                            dangerouslySetInnerHTML={{ __html: jobDetails.ai_description.slice(0, 500) + (jobDetails.ai_description.length > 500 ? '...' : '') }}
                                        />
                                    </div>
                                </div>
                            )}

                            {/* Shipping Selector */}
                            <div>
                                <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                    Shipping
                                </label>
                                <ShippingSelector
                                    value={selectedShipping || undefined}
                                    onChange={setSelectedShipping}
                                />
                            </div>

                            {/* Schedule Listing */}
                            <div className="p-3 bg-blue-50/50 rounded-xl border border-blue-100">
                                <label className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-1 block flex items-center gap-1">
                                    <CalendarClock size={12} />
                                    Schedule (Optional)
                                </label>
                                <Input
                                    type="datetime-local"
                                    value={scheduledTime}
                                    onChange={(e) => setScheduledTime(e.target.value)}
                                    className="bg-white"
                                />
                                <p className="text-[10px] text-stone-400 mt-1">Leave blank to post immediately</p>
                            </div>

                        </div>
                    ) : (
                        /* Fallback basic form if no job details */
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">Title</label>
                                <Input value={selectedJob?.name || ''} readOnly className="bg-stone-50" />
                            </div>
                            <div>
                                <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">Price</label>
                                <Input value={listingPrice} onChange={(e) => setListingPrice(e.target.value)} className="bg-stone-50" />
                            </div>
                        </div>
                    )}

                    {/* Create Listing Button */}
                    <div className="mt-6">
                        <button
                            onClick={handleCreateListing}
                            disabled={!selectedJob || isCreating}
                            className={`w-full py-3 px-4 rounded-xl font-medium text-white transition-all ${isCreating
                                ? 'bg-stone-400 cursor-wait'
                                : selectedJob
                                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 shadow-lg shadow-blue-500/25'
                                    : 'bg-stone-300 cursor-not-allowed'
                                }`}
                        >
                            {isCreating ? 'Creating...' : scheduledTime ? 'Schedule Listing' : 'Create eBay Listing'}
                        </button>

                        {createResult && (
                            <div className={`mt-2 p-2 rounded-lg text-sm ${createResult.success
                                ? 'bg-green-50 text-green-700 border border-green-200'
                                : 'bg-red-50 text-red-700 border border-red-200'
                                }`}>
                                {createResult.message}
                            </div>
                        )}
                    </div>
                </>
            )}

            {/* Live Logs Section - Only show when a job is selected */}
            {selectedJob && (
                <div className="mt-6">
                    <LogViewer
                        logs={jobLogs[selectedJob.id] || []}
                        className="h-48"
                    />
                </div>
            )}
        </div>
    </div>
)

export function Dashboard(props: DashboardProps) {
    const { selectedJob, jobs, setSelectedJob, queueStats, isProcessing, ebayStatus, handleScan, isScanning } = props

    // Local UI State for "Create Listing" flow
    const [currentStage, setCurrentStage] = useState(WorkflowStage.IMPORT)
    const [isScannerOpen, setIsScannerOpen] = useState(false)
    const [selectedShipping, setSelectedShipping] = useState<string | null>(null)
    const [listingPrice, setListingPrice] = useState<string>('29.99')
    const [listingTitle, setListingTitle] = useState<string>('')
    const [scheduledTime, setScheduledTime] = useState<string>('')
    const [isCreating, setIsCreating] = useState(false)
    const [createResult, setCreateResult] = useState<{ success: boolean; message: string } | null>(null)
    const [previewImage, setPreviewImage] = useState<string | null>(null)
    const [jobDetails, setJobDetails] = useState<JobDetails | null>(null)
    const [isLoadingDetails, setIsLoadingDetails] = useState(false)

    // Drag & Drop State
    const [isDragOver, setIsDragOver] = useState(false)
    const [dragMessage, setDragMessage] = useState<string | null>(null)
    // Bulk Selection State
    const [selectedJobIds, setSelectedJobIds] = useState<Set<string>>(new Set())
    const isSelectionMode = selectedJobIds.size > 0

    // Filter State
    const [filterStatus, setFilterStatus] = useState<'all' | 'draft' | 'active' | 'issue'>('all')

    // Filter Logic
    const filteredJobs = jobs.filter(job => {
        if (filterStatus === 'all') return true
        if (filterStatus === 'draft') return job.status === 'completed' && !job.listing_id
        if (filterStatus === 'active') return job.listing_id // Active if listing_id exists
        if (filterStatus === 'issue') return job.status === 'failed'
        return true
    })

    // Counts for tabs
    const counts = {
        all: jobs.length,
        draft: jobs.filter(j => j.status === 'completed' && !j.listing_id).length,
        active: jobs.filter(j => j.listing_id).length,
        issue: jobs.filter(j => j.status === 'failed').length
    }

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
            // Optimistic update or wait for socket event
            clearSelection()
        } catch (e) {
            console.error(e)
            alert("Failed to delete jobs")
        }
    }

    const handleBulkUpdate = async (updates: Record<string, unknown>) => {
        try {
            await fetch('/api/jobs/bulk-update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jobIds: Array.from(selectedJobIds),
                    updates
                })
            })
            clearSelection()
        } catch (e) {
            console.error(e)
            alert("Failed to update jobs")
        }
    }

    // Fetch preview image when job is selected
    useEffect(() => {
        if (selectedJob) {
            setPreviewImage(null) // Reset
            fetch(`/api/job/${selectedJob.id}/images`)
                .then(res => res.json())
                .then(data => {
                    if (data.images && data.images.length > 0) {
                        // API returns {name, url} objects - use the pre-built url
                        const firstImage = data.images[0]
                        setPreviewImage(firstImage.url || `/api/job/${selectedJob.id}/image/${firstImage.name}`)
                    }
                })
                .catch(err => console.error("Failed to load job images", err))
        }
    }, [selectedJob])

    // Fetch job details (AI analysis) when job is selected
    useEffect(() => {
        if (selectedJob) {
            setIsLoadingDetails(true)
            setJobDetails(null)
            fetchJobDetails(selectedJob.id)
                .then(details => {
                    setJobDetails(details)
                    // Pre-populate title and price from AI analysis
                    setListingTitle(details.user_title || details.ai_title || selectedJob.name)
                    if (details.suggested_price) {
                        setListingPrice(String(details.suggested_price))
                    }
                })
                .catch(err => console.error("Failed to load job details", err))
                .finally(() => setIsLoadingDetails(false))
        } else {
            setJobDetails(null)
            setListingTitle('')
            setScheduledTime('') // Reset schedule time
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


    // Drag & Drop Handlers for Queue Panel
    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        if (!isDragOver) setIsDragOver(true)
    }

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragOver(false)
    }

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragOver(false)

        const files = Array.from(e.dataTransfer.files)

        if (files.length > 0) {
            // Electron Path Access
            const firstFile = files[0] as { path?: string }
            const path = firstFile.path

            if (path) {
                setDragMessage(`Processing ${path}...`)
                try {
                    const res = await addFolderToQueue(path)
                    if (res.success) {
                        setDragMessage(`Added ${res.count} jobs from folder`)
                        setTimeout(() => setDragMessage(null), 3000)
                    } else {
                        setDragMessage(`Error: ${res.message || 'Invalid folder'}`)
                        setTimeout(() => setDragMessage(null), 3000)
                    }
                } catch {
                    setDragMessage('Failed to add folder')
                    setTimeout(() => setDragMessage(null), 3000)
                }
            } else {
                setDragMessage("Browser mode: Drag & Drop folders not supported yet.")
                setTimeout(() => setDragMessage(null), 3000)
            }
        }
    }

    // Handle successful scan from USB scanner
    const handleScannerInput = (bookData: unknown) => {
        // Log for now, future updates will create a job
        console.log("Book Scanned:", bookData);
    }

    const renderContent = (isMobileView: boolean) => (
        <>
            <ScannerListener onScan={handleScannerInput} />
            <DashboardContent
                {...props}
                isMobile={isMobileView}
                selectedJob={selectedJob}
                listingPrice={listingPrice}
                setListingPrice={setListingPrice}
                listingTitle={listingTitle}
                setListingTitle={setListingTitle}
                selectedShipping={selectedShipping}
                setSelectedShipping={setSelectedShipping}
                scheduledTime={scheduledTime}
                setScheduledTime={setScheduledTime}
                isCreating={isCreating}
                handleCreateListing={handleCreateListing}
                createResult={createResult}
                previewImage={previewImage}
                jobLogs={props.jobLogs}
                handleScanBarcode={() => setIsScannerOpen(true)}
                jobDetails={jobDetails}
                isLoadingDetails={isLoadingDetails}
            />
        </>
    )

    return (
        <div className="flex-1 flex h-full overflow-hidden relative">
            {/* Background Pattern */}
            <div className="absolute top-0 right-0 opacity-30 pointer-events-none">
                <svg width="400" height="400" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                    <path
                        fill="#84A98C"
                        d="M47.7,-58.3C60.5,-48.9,69.1,-33.4,73.1,-17.1C77.1,-0.8,76.5,16.4,68.4,29.9C60.3,43.4,44.7,53.2,28.7,60.8C12.7,68.4,-3.7,73.8,-19.4,70.9C-35.1,68,-50.1,56.8,-61.1,43C-72.1,29.2,-79.1,12.8,-76.3,-2.2C-73.5,-17.2,-60.9,-30.8,-48.4,-40.5C-35.9,-50.2,-23.5,-56.1,-9.6,-59.4C4.3,-62.7,18.6,-63.3,34.9,-67.7L47.7,-58.3Z"
                        transform="translate(100 100)"
                    />
                </svg>
            </div>

            {/* Mobile Layout */}
            <div className="md:hidden w-full h-full overflow-y-auto bg-transparent p-4 pb-36">
                {/* Mobile Header */}
                <header className="flex justify-between items-center mb-6">
                    <div>
                        <h1 className="font-display font-bold text-2xl text-stone-800">Workspace</h1>
                        <p className="text-stone-400 text-xs text-nowrap">
                            {queueStats.pending} Items Pending
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        {/* Install App Button */}
                        <InstallPrompt />

                        {/* Mobile eBay Badge */}
                        <div className={`w-2 h-2 rounded-full ${ebayStatus === 'connected' ? 'bg-blue-500' : ebayStatus === 'checking' ? 'bg-gray-300' : 'bg-red-500'}`} title={ebayStatus === 'connected' ? 'eBay Connected' : 'eBay Offline'} />

                        <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-full shadow-sm border border-stone-100">
                            <div
                                className={`w-2 h-2 rounded-full ${isProcessing ? 'bg-green-500 animate-pulse' : 'bg-stone-300'}`}
                            />
                            <span className="text-[10px] uppercase font-bold text-stone-500">
                                {isProcessing ? 'Active' : 'Ready'}
                            </span>
                        </div>
                    </div>
                </header>

                {renderContent(true)}
            </div>

            {/* Desktop Layout - Hidden on Mobile */}
            <div className="hidden md:flex flex-1 h-full w-full relative z-10">
                <ResizablePanelGroup direction="horizontal" className="w-full h-full">
                    {/* Main Content */}
                    <ResizablePanel defaultSize={75} minSize={50}>
                        <div className="flex flex-col p-8 overflow-y-auto h-full">
                            {/* Header */}
                            <header className="flex justify-between items-center mb-8">
                                <div>
                                    <h1 className="font-display font-bold text-3xl text-stone-800">Workspace</h1>
                                    <p className="text-stone-400">Manage your listings and drafts</p>
                                </div>
                                <div className="flex items-center gap-3">
                                    {/* Desktop eBay Badge */}
                                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${ebayStatus === 'connected'
                                        ? 'bg-blue-50 text-blue-700 border-blue-200'
                                        : 'bg-red-50 text-red-700 border-red-200'
                                        }`}>
                                        <div className={`w-1.5 h-1.5 rounded-full ${ebayStatus === 'connected' ? 'bg-blue-500' : 'bg-red-500'
                                            }`} />
                                        {ebayStatus === 'connected' ? 'eBay Linked' : 'eBay Offline'}
                                    </div>

                                    <div className="flex items-center gap-3 bg-white px-4 py-2 rounded-full shadow-sm border border-stone-100">
                                        <div
                                            className={`w-2 h-2 rounded-full ${isProcessing ? 'bg-green-500 animate-pulse' : 'bg-stone-300'}`}
                                        />
                                        <span className="text-xs font-medium text-stone-600">
                                            {isProcessing ? 'System Active' : 'System Ready'}
                                        </span>
                                    </div>
                                </div>
                            </header>

                            {/* Workflow Pipeline */}
                            <div className="glass-panel rounded-2xl p-4 mb-6">
                                <StageProgress currentStage={currentStage} onStageClick={setCurrentStage} />
                            </div>



                            {renderContent(false)}
                        </div>
                    </ResizablePanel>

                    <ResizableHandle withHandle />

                    {/* Queue Panel with Drop Zone */}
                    <ResizablePanel defaultSize={25} minSize={20} maxSize={40}>
                        <div
                            className={`glass-panel border-l-0 rounded-l-none flex flex-col h-full transition-colors ${isDragOver ? 'bg-blue-50/80 border-blue-300' : ''}`}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                        >
                            {/* Queue Header */}
                            <div className="p-6 border-b border-white/20 bg-transparent">
                                <div className="flex justify-between items-center mb-1">
                                    <h3 className="font-display font-bold text-lg text-stone-800">Queue</h3>
                                    <Badge variant="secondary">{queueStats.pending}</Badge>
                                </div>
                                <p className={`text-xs ${dragMessage ? 'text-blue-600 font-bold' : 'text-stone-400'}`}>
                                    {dragMessage || (isDragOver ? "Drop folder to add!" : "Drag and drop folders here")}
                                </p>

                                {/* Filter Bar */}
                                <div className="flex gap-1 mt-4 p-1 bg-stone-100 rounded-lg">
                                    <button
                                        onClick={() => setFilterStatus('all')}
                                        className={`flex-1 text-[10px] font-bold py-1.5 rounded-md transition-all ${filterStatus === 'all' ? 'bg-white shadow-sm text-stone-800' : 'text-stone-400 hover:text-stone-600'}`}
                                    >
                                        ALL ({counts.all})
                                    </button>
                                    <button
                                        onClick={() => setFilterStatus('draft')}
                                        className={`flex-1 text-[10px] font-bold py-1.5 rounded-md transition-all ${filterStatus === 'draft' ? 'bg-white shadow-sm text-amber-600' : 'text-stone-400 hover:text-stone-600'}`}
                                    >
                                        DRAFTS ({counts.draft})
                                    </button>
                                    <button
                                        onClick={() => setFilterStatus('active')}
                                        className={`flex-1 text-[10px] font-bold py-1.5 rounded-md transition-all ${filterStatus === 'active' ? 'bg-white shadow-sm text-blue-600' : 'text-stone-400 hover:text-stone-600'}`}
                                    >
                                        POSTED ({counts.active})
                                    </button>
                                </div>
                            </div>

                            {/* Queue List */}
                            <ScrollArea className="flex-1 p-4">
                                <div className="space-y-3">
                                    <AnimatePresence>
                                        {filteredJobs.map(job => (
                                            <QueueCard
                                                key={job.id}
                                                job={job}
                                                isSelected={selectedJob?.id === job.id || selectedJobIds.has(job.id)}
                                                isSelectionMode={isSelectionMode}
                                                onToggleSelect={toggleJobSelection}
                                                onClick={() => !isSelectionMode && setSelectedJob(job)}
                                            />
                                        ))}
                                    </AnimatePresence>

                                    {jobs.length === 0 && (
                                        <div className={`text-center py-10 text-stone-400 border-2 border-dashed rounded-xl flex flex-col items-center gap-2 transition-colors ${isDragOver ? 'border-blue-400 bg-blue-50/50' : 'border-stone-200'}`}>
                                            <Upload size={24} className={`opacity-50 ${isDragOver ? 'text-blue-500' : ''}`} />
                                            <p className="text-sm font-medium">{isDragOver ? "Drop it!" : "Queue is Empty"}</p>
                                            <p className="text-xs mb-2">{isDragOver ? "Adding folder..." : "Drag folders or scan inbox"}</p>
                                            <div className="flex gap-2">
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={handleScan}
                                                    disabled={isScanning}
                                                    className="border-blue-200 text-blue-600 hover:bg-blue-50"
                                                >
                                                    {isScanning ? 'Scanning...' : 'Scan Inbox'}
                                                </Button>
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => setIsScannerOpen(true)}
                                                    className="border-stone-200 hover:bg-stone-50"
                                                >
                                                    <Barcode size={16} className="mr-2" />
                                                    Barcode
                                                </Button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </ScrollArea>
                        </div>
                    </ResizablePanel>
                </ResizablePanelGroup>
            </div>

            {/* Floating Action Bar */}
            <ActionBar
                isProcessing={isProcessing}
                onStart={props.handleStart}
                onPause={props.handlePause}
                onSettings={() => console.log('Open Settings')}
            />

            <BulkActionBar
                selectedCount={selectedJobIds.size}
                onClearSelection={clearSelection}
                onDelete={handleBulkDelete}
                onUpdatePrice={() => {
                    const price = prompt("Enter new price for selected items:")
                    if (price) handleBulkUpdate({ price })
                }}
                onSetCondition={() => {
                    // Simple prompt for now, could be a modal
                    const condition = prompt("Enter condition (NEW, USED_LIKE_NEW, USED_GOOD, USED_FAIR):")
                    if (condition) handleBulkUpdate({ condition })
                }}
            />

            <ScannerModal
                isOpen={isScannerOpen}
                onOpenChange={setIsScannerOpen}
                onJobCreated={() => {
                    // Job added event handles list update
                }}
            />
        </div>
    )
}
