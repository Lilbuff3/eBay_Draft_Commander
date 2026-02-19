import { useState } from 'react'
import { CalendarClock, ChevronDown, ChevronUp } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { ImageGallery } from '@/components/ImageGallery'
import { ShippingSelector } from '@/components/ShippingSelector'
import { LogViewer, type LogEntry } from '@/components/LogViewer'
import type { Job, JobDetails } from '@/lib/api'

// Condition options matching backend CONDITION_MAP values
const CONDITION_OPTIONS = [
    { value: 'NEW', label: 'New' },
    { value: 'NEW_OTHER', label: 'New Open Box' },
    { value: 'NEW_WITH_DEFECTS', label: 'New With Defects' },
    { value: 'LIKE_NEW', label: 'Like New' },
    { value: 'USED_EXCELLENT', label: 'Used - Excellent' },
    { value: 'USED_VERY_GOOD', label: 'Used - Very Good' },
    { value: 'USED_GOOD', label: 'Used - Good' },
    { value: 'USED_ACCEPTABLE', label: 'Used - Acceptable' },
    { value: 'SELLER_REFURBISHED', label: 'Seller Refurbished' },
] as const

interface ItemDetailDrawerProps {
    open: boolean
    onClose: () => void
    job: Job | null
    jobDetails: JobDetails | null
    isLoadingDetails: boolean
    images: Array<{ name: string; url: string }>
    // Editable fields
    listingTitle: string
    setListingTitle: (title: string) => void
    listingPrice: string
    setListingPrice: (price: string) => void
    selectedCondition: string
    setSelectedCondition: (condition: string) => void
    selectedShipping: string | null
    setSelectedShipping: (id: string | null) => void
    scheduledTime: string
    setScheduledTime: (time: string) => void
    // Actions
    isCreating: boolean
    onCreateListing: () => void
    createResult: { success: boolean; message: string } | null
    // Logs
    logs: LogEntry[]
}

export function ItemDetailDrawer({
    open,
    onClose,
    job,
    jobDetails,
    isLoadingDetails,
    images,
    listingTitle,
    setListingTitle,
    listingPrice,
    setListingPrice,
    selectedCondition,
    setSelectedCondition,
    selectedShipping,
    setSelectedShipping,
    scheduledTime,
    setScheduledTime,
    isCreating,
    onCreateListing,
    createResult,
    logs,
}: ItemDetailDrawerProps) {
    const [showLogs, setShowLogs] = useState(false)

    return (
        <Sheet open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose() }}>
            <SheetContent side="right" className="sm:max-w-xl w-full overflow-hidden flex flex-col p-0">
                <SheetHeader className="px-6 pt-6 pb-2 flex-shrink-0">
                    <SheetTitle className="text-lg font-display">
                        {job?.name || 'Item Details'}
                    </SheetTitle>
                    <SheetDescription>
                        Review and edit before listing
                    </SheetDescription>
                </SheetHeader>

                <ScrollArea className="flex-1">
                    <div className="px-6 pb-6 space-y-5">
                        {/* Image Gallery */}
                        {job && (
                            <ImageGallery
                                images={images}
                                jobId={job.id}
                            />
                        )}

                        {/* Loading State */}
                        {isLoadingDetails && (
                            <div className="flex items-center justify-center py-8">
                                <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
                                <span className="ml-2 text-stone-500">Loading analysis...</span>
                            </div>
                        )}

                        {/* Detail Form */}
                        {jobDetails && (
                            <>
                                {/* Title */}
                                <div>
                                    <div className="flex justify-between items-center mb-1">
                                        <label className="text-xs font-bold text-stone-400 uppercase tracking-wider">
                                            Title
                                        </label>
                                        <span className={`text-[10px] font-bold ${listingTitle.length >= 80 ? 'text-red-500' : 'text-stone-300'}`}>
                                            {listingTitle.length}/80
                                        </span>
                                    </div>
                                    <Input
                                        placeholder="Item Title..."
                                        value={listingTitle}
                                        onChange={(e) => setListingTitle(e.target.value)}
                                        maxLength={80}
                                        className="bg-stone-50 font-medium"
                                    />
                                </div>

                                {/* Price + Category */}
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
                                <div>
                                    <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                        Condition
                                    </label>
                                    <Select value={selectedCondition} onValueChange={setSelectedCondition}>
                                        <SelectTrigger className="bg-stone-50">
                                            <SelectValue placeholder="Select condition..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {CONDITION_OPTIONS.map(opt => (
                                                <SelectItem key={opt.value} value={opt.value}>
                                                    {opt.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

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
                                                <p className="text-[10px] text-stone-400 mt-2">
                                                    +{Object.keys(jobDetails.item_specifics).length - 8} more
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {/* Description */}
                                {jobDetails.ai_description && (
                                    <div>
                                        <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-2 block">
                                            Description
                                        </label>
                                        <div className="bg-stone-50 rounded-xl p-3 border border-stone-100 max-h-32 overflow-y-auto">
                                            <div
                                                className="text-sm text-stone-600 prose prose-sm max-w-none"
                                                dangerouslySetInnerHTML={{
                                                    __html: jobDetails.ai_description.slice(0, 500) +
                                                        (jobDetails.ai_description.length > 500 ? '...' : '')
                                                }}
                                            />
                                        </div>
                                    </div>
                                )}

                                {/* Shipping */}
                                <div>
                                    <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                        Shipping
                                    </label>
                                    <ShippingSelector
                                        value={selectedShipping || undefined}
                                        onChange={setSelectedShipping}
                                    />
                                </div>

                                {/* Schedule */}
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
                            </>
                        )}

                        {/* Fallback form */}
                        {!isLoadingDetails && !jobDetails && job && (
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">Title</label>
                                    <Input value={job.name || ''} readOnly className="bg-stone-50" />
                                </div>
                                <div>
                                    <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">Price</label>
                                    <Input value={listingPrice} onChange={(e) => setListingPrice(e.target.value)} className="bg-stone-50" />
                                </div>
                            </div>
                        )}

                        {/* Create Listing Button */}
                        {job && (
                            <div>
                                <button
                                    onClick={onCreateListing}
                                    disabled={isCreating}
                                    className={`w-full py-3 px-4 rounded-xl font-medium text-white transition-all ${
                                        isCreating
                                            ? 'bg-stone-400 cursor-wait'
                                            : 'bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 shadow-lg shadow-blue-500/25'
                                    }`}
                                >
                                    {isCreating ? 'Creating...' : scheduledTime ? 'Schedule Listing' : 'Create eBay Listing'}
                                </button>

                                {createResult && (
                                    <div className={`mt-2 p-2 rounded-lg text-sm ${
                                        createResult.success
                                            ? 'bg-green-50 text-green-700 border border-green-200'
                                            : 'bg-red-50 text-red-700 border border-red-200'
                                    }`}>
                                        {createResult.message}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Collapsible Logs */}
                        {job && (
                            <div>
                                <button
                                    onClick={() => setShowLogs(!showLogs)}
                                    className="flex items-center gap-2 text-xs font-bold text-stone-400 uppercase tracking-wider hover:text-stone-600 transition-colors w-full"
                                >
                                    {showLogs ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                    Activity Log ({logs.length} events)
                                </button>
                                {showLogs && (
                                    <div className="mt-2">
                                        <LogViewer logs={logs} className="h-48" />
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </ScrollArea>
            </SheetContent>
        </Sheet>
    )
}
