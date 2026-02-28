import { useState, useEffect, useRef, useCallback } from 'react'
import { ChevronDown, ChevronUp, AlertCircle, Loader2, Check, Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { ImageGallery } from '@/components/ImageGallery'
import { ShippingSelector } from '@/components/ShippingSelector'
import { LogViewer, type LogEntry } from '@/components/LogViewer'
import type { Job, JobDetails, ItemDraft, CategorySuggestion } from '@/lib/api'
import { searchCategories } from '@/lib/api'
import { ItemDescriptionCard } from './item-detail/ItemDescriptionCard'
import { ItemScheduleField } from './item-detail/ItemScheduleField'

// Condition options synced with backend CONDITION_MAP (constants.py)
const CONDITION_OPTIONS = [
    { value: 'NEW', label: 'New' },
    { value: 'NEW_OTHER', label: 'New Open Box' },
    { value: 'NEW_WITH_DEFECTS', label: 'New With Defects' },
    { value: 'CERTIFIED_REFURBISHED', label: 'Certified Refurbished' },
    { value: 'EXCELLENT_REFURBISHED', label: 'Excellent - Refurbished' },
    { value: 'VERY_GOOD_REFURBISHED', label: 'Very Good - Refurbished' },
    { value: 'GOOD_REFURBISHED', label: 'Good - Refurbished' },
    { value: 'SELLER_REFURBISHED', label: 'Seller Refurbished' },
    { value: 'LIKE_NEW', label: 'Like New' },
    { value: 'USED_EXCELLENT', label: 'Used - Excellent' },
    { value: 'USED_VERY_GOOD', label: 'Used - Very Good' },
    { value: 'USED_GOOD', label: 'Used - Good' },
    { value: 'USED_ACCEPTABLE', label: 'Used - Acceptable' },
    { value: 'FOR_PARTS_OR_NOT_WORKING', label: 'For Parts / Not Working' },
] as const

// Mobile detection hook for bottom-sheet behavior
function useIsMobile(breakpoint = 768) {
    const [isMobile, setIsMobile] = useState(() => window.innerWidth < breakpoint)

    useEffect(() => {
        const mql = window.matchMedia(`(max-width: ${breakpoint - 1}px)`)
        const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
        mql.addEventListener('change', handler)
        return () => mql.removeEventListener('change', handler)
    }, [breakpoint])

    return isMobile
}

interface ItemDetailDrawerProps {
    open: boolean
    onClose: () => void
    job: Job | null
    jobDetails: JobDetails | null
    isLoadingDetails: boolean
    images: Array<{ name: string; url: string }>
    // Editable fields
    draft: ItemDraft
    updateDraft: (updates: Partial<ItemDraft>) => void
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
    draft,
    updateDraft,
    isCreating,
    onCreateListing,
    createResult,
    logs,
}: ItemDetailDrawerProps) {
    const [showLogs, setShowLogs] = useState(false)
    const [showCategorySearch, setShowCategorySearch] = useState(false)
    const [categoryQuery, setCategoryQuery] = useState('')
    const [categorySuggestions, setCategorySuggestions] = useState<CategorySuggestion[]>([])
    const [isSearchingCategories, setIsSearchingCategories] = useState(false)
    const categorySearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
    const isMobile = useIsMobile()

    const handleCategorySearch = useCallback((query: string) => {
        setCategoryQuery(query)
        if (categorySearchTimer.current) clearTimeout(categorySearchTimer.current)
        if (query.length < 2) {
            setCategorySuggestions([])
            return
        }
        setIsSearchingCategories(true)
        categorySearchTimer.current = setTimeout(async () => {
            try {
                const results = await searchCategories(query)
                setCategorySuggestions(results)
            } catch {
                setCategorySuggestions([])
            } finally {
                setIsSearchingCategories(false)
            }
        }, 400)
    }, [])

    const selectCategory = useCallback((suggestion: CategorySuggestion) => {
        updateDraft({
            categoryId: suggestion.category_id,
            categoryName: suggestion.category_name
        })
        setShowCategorySearch(false)
        setCategoryQuery('')
        setCategorySuggestions([])
    }, [updateDraft])

    const sheetSide = isMobile ? 'bottom' : 'right'

    return (
        <Sheet open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose() }}>
            <SheetContent
                side={sheetSide}
                className={
                    isMobile
                        ? "w-full h-[85vh] rounded-t-2xl overflow-hidden flex flex-col p-0"
                        : "sm:max-w-xl w-full overflow-hidden flex flex-col p-0"
                }
            >
                {/* Swipe indicator handle — mobile only */}
                {isMobile && (
                    <div className="flex justify-center pt-2 pb-0 flex-shrink-0">
                        <div className="w-10 h-1.5 bg-stone-300 rounded-full" />
                    </div>
                )}

                <SheetHeader className="px-6 pt-4 pb-2 flex-shrink-0">
                    <SheetTitle className="text-lg font-display">
                        {job?.name || 'Item Details'}
                    </SheetTitle>
                    <SheetDescription>
                        Review and edit before listing
                    </SheetDescription>
                </SheetHeader>

                <ScrollArea className="flex-1 min-h-0">
                    <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
                        {/* Needs Review Alert */}
                        {job?.status === 'needs_review' && (
                            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 text-amber-800">
                                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-sm font-bold">Action Required</p>
                                    <p className="text-xs opacity-90">{job.error_message || "Missing mandatory item specifics."}</p>
                                </div>
                            </div>
                        )}

                        {!isLoadingDetails && jobDetails && (
                            <>
                                {/* Images */}
                                {job && (
                                    <ImageGallery
                                        images={images}
                                        jobId={job.id}
                                    />
                                )}

                                {/* Title */}
                                <div>
                                    <div className="flex justify-between items-center mb-1">
                                        <label htmlFor="listing-title" className="text-xs font-bold text-stone-400 uppercase tracking-wider">
                                            Title
                                        </label>
                                        <span className={`text-[10px] font-bold ${draft.title.length >= 80 ? 'text-red-500' : 'text-stone-300'}`}>
                                            {draft.title.length}/80
                                        </span>
                                    </div>
                                    <Input
                                        id="listing-title"
                                        placeholder="Item Title..."
                                        value={draft.title}
                                        onChange={(e) => updateDraft({ title: e.target.value })}
                                        maxLength={80}
                                        className="bg-stone-50 font-medium"
                                    />
                                </div>

                                {/* Price + Category */}
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label htmlFor="listing-price" className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                            Price
                                        </label>
                                        <div className="relative">
                                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400">$</span>
                                            <Input
                                                id="listing-price"
                                                placeholder="0.00"
                                                className="bg-stone-50 pl-7"
                                                value={draft.price}
                                                onChange={(e) => updateDraft({ price: e.target.value })}
                                            />
                                        </div>
                                        {jobDetails.pricing_data?.price_source && (
                                            <p className="text-[10px] text-stone-400 mt-1">
                                                {jobDetails.pricing_data.price_source}
                                            </p>
                                        )}
                                    </div>
                                    <div className="relative">
                                        <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                            Category
                                        </label>
                                        {showCategorySearch ? (
                                            <div>
                                                <div className="relative">
                                                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400" />
                                                    <Input
                                                        autoFocus
                                                        placeholder="Search categories..."
                                                        value={categoryQuery}
                                                        onChange={(e) => handleCategorySearch(e.target.value)}
                                                        onBlur={() => setTimeout(() => setShowCategorySearch(false), 200)}
                                                        className="bg-white pl-8 h-9 text-sm"
                                                    />
                                                    {isSearchingCategories && (
                                                        <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 animate-spin text-stone-400" />
                                                    )}
                                                </div>
                                                {categorySuggestions.length > 0 && (
                                                    <div className="absolute z-50 mt-1 w-full bg-white border border-stone-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                                                        {categorySuggestions.map((sug) => (
                                                            <button
                                                                key={sug.category_id}
                                                                onMouseDown={() => selectCategory(sug)}
                                                                className="w-full text-left px-3 py-2 hover:bg-blue-50 border-b border-stone-100 last:border-0"
                                                            >
                                                                <div className="text-sm font-medium text-stone-800">{sug.category_name}</div>
                                                                <div className="text-[10px] text-stone-400 truncate">{sug.full_path}</div>
                                                            </button>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <button
                                                onClick={() => setShowCategorySearch(true)}
                                                className="w-full text-left bg-stone-50 rounded-lg px-3 py-2 text-sm text-stone-600 border border-stone-200 hover:border-blue-300 hover:bg-blue-50/30 transition-colors"
                                            >
                                                {draft.categoryName || draft.categoryId || jobDetails.category_name || jobDetails.category_id || 'Click to search...'}
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {/* Condition */}
                                <div>
                                    <label htmlFor="listing-condition" className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                        Condition
                                    </label>
                                    <Select value={draft.condition} onValueChange={(v: string) => updateDraft({ condition: v })}>
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
                                <div className="space-y-3">
                                    <div className="flex justify-between items-center">
                                        <label className="text-xs font-bold text-stone-400 uppercase tracking-wider block">
                                            Item Specifics
                                        </label>
                                        <span className="text-[10px] text-stone-400">Click to edit</span>
                                    </div>
                                    <div className="grid grid-cols-1 gap-2">
                                        {Object.entries(draft.itemSpecifics).map(([key, value]) => {
                                            const requiredAspect = jobDetails.ebay_required_aspects?.find(a => a.name === key)
                                            const isRequired = !!requiredAspect
                                            const hasEnumValues = requiredAspect && requiredAspect.values.length > 0

                                            return (
                                                <div key={key} className="flex gap-2 items-center">
                                                    <span className={`text-xs font-medium w-24 flex-shrink-0 truncate ${isRequired ? 'text-amber-600' : 'text-stone-500'}`}>
                                                        {key}{isRequired && <span className="text-red-500">*</span>}:
                                                    </span>
                                                    {hasEnumValues ? (
                                                        <Select value={value} onValueChange={(v: string) => {
                                                            const newSpecs = { ...draft.itemSpecifics, [key]: v };
                                                            updateDraft({ itemSpecifics: newSpecs });
                                                        }}>
                                                            <SelectTrigger className="h-8 text-sm bg-stone-50 border-stone-200">
                                                                <SelectValue placeholder="Select..." />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {requiredAspect.values.map((v: string) => (
                                                                    <SelectItem key={v} value={v}>{v}</SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                    ) : (
                                                        <Input
                                                            value={value}
                                                            onChange={(e) => {
                                                                const newSpecs = { ...draft.itemSpecifics, [key]: e.target.value };
                                                                updateDraft({ itemSpecifics: newSpecs });
                                                            }}
                                                            className={`h-8 py-0 px-2 text-sm bg-stone-50 focus:bg-white ${isRequired && !value ? 'border-amber-300' : 'border-stone-200'}`}
                                                        />
                                                    )}
                                                </div>
                                            )
                                        })}
                                    </div>
                                </div>

                                {/* Description */}
                                <ItemDescriptionCard description={jobDetails.ai_description} />

                                {/* Shipping */}
                                <div>
                                    <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-1 block">
                                        Shipping
                                    </label>
                                    <ShippingSelector
                                        value={draft.shipping || undefined}
                                        onChange={(v) => updateDraft({ shipping: v })}
                                    />
                                </div>

                                {/* Schedule */}
                                <ItemScheduleField scheduledTime={draft.scheduledTime} updateDraft={updateDraft} />
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
                                    <Input value={draft.price} onChange={(e) => updateDraft({ price: e.target.value })} className="bg-stone-50" />
                                </div>
                            </div>
                        )}

                        {/* Collapsible Logs */}
                        {job && (
                            <div className="pb-2">
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

                {/* Sticky CTA — always visible at bottom of drawer */}
                {job && (
                    <div className="flex-shrink-0 border-t border-stone-100 px-6 py-3 bg-white pb-safe">
                        <button
                            onClick={onCreateListing}
                            disabled={isCreating}
                            className={`w-full py-3 px-4 rounded-xl font-medium text-white transition-all ${isCreating
                                ? 'bg-stone-400 cursor-wait'
                                : 'bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 shadow-lg shadow-blue-500/25'
                                }`}
                        >
                            {isCreating ? (
                                <span className="flex items-center justify-center gap-2">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Creating...
                                </span>
                            ) : createResult?.success ? (
                                <span className="flex items-center justify-center gap-2">
                                    <Check className="w-4 h-4" />
                                    Listed Successfully
                                </span>
                            ) : (
                                draft.scheduledTime ? 'Schedule Listing' : 'Create eBay Listing'
                            )}
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
                )}
            </SheetContent>
        </Sheet>
    )
}
