import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Camera, Search, LayoutTemplate, Eye, Image, Upload, Package, ArrowLeft } from 'lucide-react'
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StageProgress, WorkflowStage } from '@/components/StageProgress'
import { QueueCard } from '@/components/QueueCard'
import { ToolCard } from '@/components/ToolCard'
import { ActionBar } from '@/components/ActionBar'
import { PhotoEditor } from '@/components/PhotoEditor'
import { PriceResearch } from '@/components/PriceResearch'
import { TemplateManager } from '@/components/TemplateManager'
import { PreviewPanel } from '@/components/PreviewPanel'
import { ShippingSelector } from '@/components/ShippingSelector'
import { SalesWidget } from '@/components/SalesWidget'
import { ActiveListings } from '@/components/ActiveListings'
import { UploadZone } from '@/components/UploadZone'
import { InstallPrompt } from '@/components/InstallPrompt'
import { fetchJobs, fetchStatus, startQueue, pauseQueue, createListing, type Job, type QueueStats } from '@/lib/api'

type ActiveTool = 'photo-editor' | 'price-research' | 'templates' | 'preview' | 'inventory' | null

export function Dashboard() {
    const [jobs, setJobs] = useState<Job[]>([])
    const [selectedJob, setSelectedJob] = useState<Job | null>(null)
    const [queueStats, setQueueStats] = useState<QueueStats>({ pending: 0, completed: 0, failed: 0, total: 0 })
    const [isProcessing, setIsProcessing] = useState(false)
    const [currentStage, setCurrentStage] = useState(WorkflowStage.EDIT)
    const [activeTool, setActiveTool] = useState<ActiveTool>(null)
    const [selectedShipping, setSelectedShipping] = useState<string | null>(null)
    const [listingPrice, setListingPrice] = useState<string>('29.99')
    const [isCreating, setIsCreating] = useState(false)
    const [createResult, setCreateResult] = useState<{ success: boolean; message: string } | null>(null)
    const [ebayStatus, setEbayStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking')

    // Poll for real data
    useEffect(() => {
        const fetchData = async () => {
            try {
                const [jobsData, statusData] = await Promise.all([
                    fetchJobs(),
                    fetchStatus()
                ])

                setJobs(jobsData)
                setQueueStats(statusData.stats)
                setIsProcessing(statusData.status === 'processing')

                if (!selectedJob && jobsData.length > 0) {
                    setSelectedJob(jobsData[0])
                }
            } catch (err) {
                console.error('Fetch error:', err)
            }
        }

        const checkEbay = async () => {
            try {
                const res = await fetch('/api/ebay/status')
                const data = await res.json()
                setEbayStatus(data.status === 'connected' ? 'connected' : 'disconnected')
            } catch (e) {
                setEbayStatus('disconnected')
            }
        }

        fetchData()
        checkEbay()

        const interval = setInterval(fetchData, 2000)
        const ebayInterval = setInterval(checkEbay, 30000) // Check eBay every 30s

        return () => {
            clearInterval(interval)
            clearInterval(ebayInterval)
        }
    }, [selectedJob])

    const handleStart = async () => {
        try {
            await startQueue()
            setIsProcessing(true)
        } catch (e) {
            console.error(e)
        }
    }

    const handlePause = async () => {
        try {
            await pauseQueue()
            setIsProcessing(false)
        } catch (e) {
            console.error(e)
        }
    }

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

    // --- Components for Layouts ---

    const DashboardContent = ({ isMobile = false }) => (
        <div className={`grid ${isMobile ? 'grid-cols-1 flex flex-col' : 'grid-cols-12'} gap-6 mb-24`}>
            {/* Hero Image Section */}
            <div className={`${isMobile ? 'w-full order-1' : 'col-span-8'} bg-white rounded-3xl p-6 shadow-sm border border-stone-100 relative group overflow-hidden`}>
                {!selectedJob ? (
                    /* Show Upload Zone when no job selected */
                    <div className="py-8">
                        <h2 className="text-xl font-semibold text-stone-700 mb-4 text-center">Step 1: Add Photos</h2>
                        <UploadZone onUploadComplete={() => { }} />
                        <p className="text-center text-stone-400 text-sm mt-4">Upload product photos to create a new listing</p>
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
                            <div className="text-stone-300 flex flex-col items-center">
                                <Image size={48} />
                                <span className="text-sm font-medium mt-2">{selectedJob.name}</span>
                            </div>
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

            {/* Tools & Stats Section */}
            <AnimatePresence mode="wait">
                {!activeTool ? (
                    <motion.div
                        key="tools-grid"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0, height: 0 }}
                        className={`${isMobile ? 'order-2 w-full' : 'col-span-4'} flex flex-col gap-6`}
                    >
                        <div className="grid grid-cols-2 gap-3">
                            <ToolCard
                                icon={Camera}
                                title="Photo Editor"
                                description="Enhance"
                                color="bg-blue-500"
                                onClick={() => setActiveTool('photo-editor')}
                            />
                            <ToolCard
                                icon={Search}
                                title="Research"
                                description="Prices"
                                color="bg-emerald-500"
                                onClick={() => setActiveTool('price-research')}
                            />
                            <ToolCard
                                icon={LayoutTemplate}
                                title="Templates"
                                description="Presets"
                                color="bg-purple-500"
                                onClick={() => setActiveTool('templates')}
                            />
                            <ToolCard
                                icon={Eye}
                                title="Preview"
                                description="Check"
                                color="bg-orange-500"
                                onClick={() => setActiveTool('preview')}
                            />
                            <ToolCard
                                icon={Package}
                                title="Inventory"
                                description="Listings"
                                color="bg-indigo-500"
                                onClick={() => setActiveTool('inventory')}
                            />
                        </div>

                        <SalesWidget />
                    </motion.div>
                ) : (
                    <motion.div
                        key="tools-compact"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className={`${isMobile ? 'order-2 w-full' : 'col-span-4'} flex gap-2 overflow-x-auto pb-2 scrollbar-none`}
                    >
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setActiveTool(null)}
                            className="shrink-0"
                        >
                            <ArrowLeft size={16} className="mr-1" /> Back
                        </Button>
                        {[
                            { id: 'photo-editor', icon: Camera, label: 'Photos', color: 'bg-blue-500' },
                            { id: 'price-research', icon: Search, label: 'Prices', color: 'bg-emerald-500' },
                            { id: 'templates', icon: LayoutTemplate, label: 'Templates', color: 'bg-purple-500' },
                            { id: 'preview', icon: Eye, label: 'Preview', color: 'bg-orange-500' },
                            { id: 'inventory', icon: Package, label: 'Inventory', color: 'bg-indigo-500' },
                        ].map(tool => (
                            <button
                                key={tool.id}
                                onClick={() => setActiveTool(tool.id as ActiveTool)}
                                className={`p-2 rounded-lg border flex items-center justify-center gap-2 transition-all whitespace-nowrap px-3 ${activeTool === tool.id
                                    ? `${tool.color} text-white border-transparent`
                                    : 'bg-white border-stone-200 hover:bg-stone-50'
                                    }`}
                            >
                                <tool.icon size={16} />
                                <span className="text-xs font-medium">{tool.label}</span>
                            </button>
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Active Tool Panel */}
            <AnimatePresence>
                {activeTool && (
                    <motion.div
                        key="tool-panel"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 20 }}
                        className={`${isMobile ? 'order-3 w-full' : 'col-span-12'}`}
                    >
                        {activeTool === 'photo-editor' && (
                            <PhotoEditor
                                jobId={selectedJob?.id}
                                onClose={() => setActiveTool(null)}
                            />
                        )}
                        {activeTool === 'price-research' && (
                            <PriceResearch
                                jobId={selectedJob?.id}
                                initialQuery={selectedJob?.name}
                                onClose={() => setActiveTool(null)}
                            />
                        )}
                        {activeTool === 'templates' && (
                            <TemplateManager
                                onClose={() => setActiveTool(null)}
                            />
                        )}
                        {activeTool === 'preview' && (
                            <PreviewPanel
                                jobId={selectedJob?.id}
                                onClose={() => setActiveTool(null)}
                            />
                        )}
                        {activeTool === 'inventory' && (
                            <ActiveListings
                                onClose={() => setActiveTool(null)}
                            />
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
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
            <div className="md:hidden w-full h-full overflow-y-auto bg-stone-50 p-4 pb-24">
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

                <DashboardContent isMobile={true} />
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

                            <DashboardContent isMobile={false} />
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
                                        <div className="text-center py-10 text-stone-400 border-2 border-dashed border-stone-200 rounded-xl">
                                            <Upload size={24} className="mx-auto mb-2 opacity-50" />
                                            <p className="text-sm">Empty Queue</p>
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
                onStart={handleStart}
                onPause={handlePause}
                onSettings={() => console.log('Open Settings')}
            />
        </div>
    )
}
