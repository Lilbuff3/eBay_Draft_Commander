import { useState, useEffect } from 'react'
import { AnimatePresence } from 'framer-motion'
import { Camera, Search, Image, Upload } from 'lucide-react'
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StageProgress, WorkflowStage } from '@/components/StageProgress'
import { QueueCard } from '@/components/QueueCard'
import { ActionBar } from '@/components/ActionBar'
import { ShippingSelector } from '@/components/ShippingSelector'
import { UploadZone } from '@/components/UploadZone'
import { InstallPrompt } from '@/components/InstallPrompt'
import { createListing, type Job, type QueueStats } from '@/lib/api'
import { ScannerListener } from '@/components/ScannerListener'

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
}

interface DashboardContentProps extends DashboardProps {
    isMobile: boolean
    listingPrice: string
    setListingPrice: (price: string) => void
    selectedShipping: string | null
    setSelectedShipping: (id: string | null) => void
    isCreating: boolean
    handleCreateListing: () => void
    createResult: { success: boolean; message: string } | null
    previewImage?: string | null
}

const DashboardContent = ({
    isMobile = false,
    selectedJob,
    listingPrice,
    setListingPrice,
    selectedShipping,
    setSelectedShipping,
    isCreating,
    handleCreateListing,
    createResult,
    handleScan,
    isScanning,
    scanMessage,
    previewImage
}: DashboardContentProps) => (
    <div className={`grid ${isMobile ? 'grid-cols-1 flex flex-col' : 'grid-cols-12'} gap-6 mb-24`}>
        {/* Hero Image Section */}
        <div className={`${isMobile ? 'w-full order-1' : 'col-span-12'} bg-white rounded-3xl p-6 shadow-sm border border-stone-100 relative group overflow-hidden`}>
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
                        <button className="bg-black/50 hover:bg-black/70 text-white p-2 rounded-lg backdrop-blur-sm">
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

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                Title
                            </label>
                            <Input
                                placeholder="Item Title..."
                                value={selectedJob?.name || ''}
                                readOnly
                                className="bg-stone-50"
                            />
                        </div>
                        <div>
                            <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                Price
                            </label>
                            <Input
                                placeholder="$0.00"
                                className="bg-stone-50"
                                value={listingPrice}
                                onChange={(e) => setListingPrice(e.target.value)}
                            />
                        </div>
                    </div>

                    {/* Shipping Selector */}
                    <div className="mt-4">
                        <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                            Shipping
                        </label>
                        <ShippingSelector
                            value={selectedShipping || undefined}
                            onChange={setSelectedShipping}
                        />
                    </div>

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
                            {isCreating ? 'Creating...' : 'Create eBay Listing'}
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
        </div>
    </div>
)

export function Dashboard(props: DashboardProps) {
    const { selectedJob, jobs, setSelectedJob, queueStats, isProcessing, ebayStatus, handleScan, isScanning, scanMessage } = props

    // Local UI State for "Create Listing" flow
    const [currentStage, setCurrentStage] = useState(WorkflowStage.IMPORT)
    const [selectedShipping, setSelectedShipping] = useState<string | null>(null)
    const [listingPrice, setListingPrice] = useState<string>('29.99')
    const [isCreating, setIsCreating] = useState(false)
    const [createResult, setCreateResult] = useState<{ success: boolean; message: string } | null>(null)
    const [previewImage, setPreviewImage] = useState<string | null>(null)

    // Fetch preview image when job is selected
    useEffect(() => {
        if (selectedJob) {
            setPreviewImage(null) // Reset
            fetch(`/api/job/${selectedJob.id}/images`)
                .then(res => res.json())
                .then(data => {
                    if (data.images && data.images.length > 0) {
                        setPreviewImage(`/api/job/${selectedJob.id}/image/${data.images[0]}`)
                    }
                })
                .catch(err => console.error("Failed to load job images", err))
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
                fulfillmentPolicy: selectedShipping || undefined
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

    // Handle successful scan from USB scanner
    const handleScannerInput = (bookData: any) => {
        // Log for now, future updates will create a job
        console.log("Book Scanned:", bookData);
    }

    const renderContent = (isMobile: boolean) => (
        <>
            <ScannerListener onScan={handleScannerInput} />
            <DashboardContent
                {...props}
                isMobile={isMobile}
                listingPrice={listingPrice}
                setListingPrice={setListingPrice}
                selectedShipping={selectedShipping}
                setSelectedShipping={setSelectedShipping}
                isCreating={isCreating}
                handleCreateListing={handleCreateListing}
                createResult={createResult}
                isScanning={isScanning}
                scanMessage={scanMessage}
                previewImage={previewImage}
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
            <div className="md:hidden w-full h-full overflow-y-auto bg-stone-50 p-4 pb-36">
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
                <ResizablePanelGroup orientation="horizontal" className="w-full h-full">
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
                            <div className="bg-white rounded-2xl p-4 shadow-sm mb-6 border border-stone-100">
                                <StageProgress currentStage={currentStage} onStageClick={setCurrentStage} />
                            </div>

                            {renderContent(false)}
                        </div>
                    </ResizablePanel>

                    <ResizableHandle withHandle />

                    {/* Queue Panel */}
                    <ResizablePanel defaultSize={25} minSize={20} maxSize={40}>
                        <div className="bg-stone-50 border-l border-stone-200 flex flex-col h-full">
                            {/* Queue Header */}
                            <div className="p-6 border-b border-stone-200 bg-white">
                                <div className="flex justify-between items-center mb-1">
                                    <h3 className="font-display font-bold text-lg text-stone-800">Queue</h3>
                                    <Badge variant="secondary">{queueStats.pending}</Badge>
                                </div>
                                <p className="text-xs text-stone-400">Drag and drop folders here</p>
                            </div>

                            {/* Queue List */}
                            <ScrollArea className="flex-1 p-4">
                                <div className="space-y-3">
                                    <AnimatePresence>
                                        {jobs.map(job => (
                                            <QueueCard
                                                key={job.id}
                                                job={job}
                                                isSelected={selectedJob?.id === job.id}
                                                onClick={() => setSelectedJob(job)}
                                            />
                                        ))}
                                    </AnimatePresence>

                                    {jobs.length === 0 && (
                                        <div className="text-center py-10 text-stone-400 border-2 border-dashed border-stone-200 rounded-xl flex flex-col items-center gap-2">
                                            <Upload size={24} className="opacity-50" />
                                            <p className="text-sm font-medium">Queue is Empty</p>
                                            <p className="text-xs mb-2">Drag folders or scan inbox</p>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={handleScan}
                                                disabled={isScanning}
                                                className="border-blue-200 text-blue-600 hover:bg-blue-50"
                                            >
                                                {isScanning ? 'Scanning...' : 'Scan Inbox'}
                                            </Button>
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
        </div>
    )
}
