import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    CheckCircle,
    Trash2,
    Edit3,
    ArrowRight,
    ArrowLeft,
    TrendingUp,
    ShieldAlert,
    ShieldCheck,
    Tag,
    ListFilter,
    Check,
    AlertCircle
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useHaptics } from '@/hooks/useHaptics'
import type { Job } from '@/lib/api'

const SHIPPING_PRESETS = [
    { label: 'Standard', cost: 6.50 },
    { label: 'Small Pkg', cost: 4.50 },
    { label: 'Media Mail', cost: 4.00 },
    { label: 'Large / Heavy', cost: 10.00 },
]

const CONDITIONS = [
    { label: 'Brand New', value: 'Brand New' },
    { label: 'Like New', value: 'Like New' },
    { label: 'Very Good', value: 'Used - Very Good' },
    { label: 'Good', value: 'Used - Good' },
    { label: 'Acceptable', value: 'Used - Acceptable' },
    { label: 'For Parts', value: 'For parts or not working' },
]

interface MobileReviewDeckProps {
    listings: Job[]
    onApprove: (ids: string[]) => Promise<void>
    onUpdate: (id: string, updates: { title?: string; price?: string; condition?: string; cogs?: number }) => Promise<void>
    onDelete: (id: string) => Promise<void>
    onOpenFullDetail?: (listing: Job) => void
    onSwitchToList?: () => void
}

export function MobileReviewDeck({
    listings,
    onApprove,
    onUpdate,
    onDelete,
    onOpenFullDetail,
    onSwitchToList,
}: MobileReviewDeckProps) {
    const [currentIndex, setCurrentIndex] = useState(0)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [approvedCount, setApprovedCount] = useState(0)
    const [sessionNetProfit, setSessionNetProfit] = useState(0)

    const { tap, success: successHaptic, error: errorHaptic, warning } = useHaptics()

    // Clamp index if list changes
    useEffect(() => {
        if (currentIndex >= listings.length && listings.length > 0) {
            setCurrentIndex(listings.length - 1)
        }
    }, [listings.length, currentIndex])

    const currentItem = listings[currentIndex]

    // Form fields for active card
    const [title, setTitle] = useState('')
    const [price, setPrice] = useState('')
    const [condition, setCondition] = useState('')
    const [cogs, setCogs] = useState('')
    const [shippingCost, setShippingCost] = useState(6.50)

    // Sync state when active card changes
    useEffect(() => {
        if (currentItem) {
            const ai = (currentItem.ai_data || {}) as Record<string, any>
            setTitle(currentItem.display_name || currentItem.name || '')
            setPrice(currentItem.price || ai.suggested_price || ai.price || '0.00')
            setCondition(currentItem.condition || (ai.condition?.state ?? ai.condition ?? 'Used - Good'))
            const rawCogs = currentItem.cogs ?? ai.cogs
            setCogs(rawCogs !== undefined && rawCogs !== null ? String(rawCogs) : '')
            setShippingCost(ai.shipping_cost ? parseFloat(ai.shipping_cost) : 6.50)
        }
    }, [currentItem])

    if (listings.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-20 px-6 text-center bg-paper-card border-2 border-dashed border-stone-200 rounded-3xl animate-in fade-in">
                <div className="w-20 h-20 bg-sage-100 rounded-full flex items-center justify-center mb-4 text-sage-600 shadow-inner">
                    <Check size={36} className="stroke-[3]" />
                </div>
                <h2 className="text-2xl font-display font-bold text-ink-800 tracking-tight">All Caught Up!</h2>
                <p className="text-stone-500 max-w-sm mt-1 mb-6 text-sm">
                    {approvedCount > 0
                        ? `You approved ${approvedCount} listing${approvedCount !== 1 ? 's' : ''} with ~$${sessionNetProfit.toFixed(2)} in expected net profit!`
                        : 'No pending listings in the review queue.'}
                </p>
                {onSwitchToList && (
                    <Button variant="outline" onClick={onSwitchToList} className="rounded-2xl h-12 px-6 font-semibold">
                        View List View
                    </Button>
                )}
            </div>
        )
    }

    // Profit calculations
    const priceNum = parseFloat(price) || 0
    const cogsNum = cogs.trim() !== '' ? parseFloat(cogs) : 0
    const ebayFee = Math.round(priceNum * 0.1325 * 100) / 100
    const paymentFee = priceNum > 0 ? 0.30 : 0
    const takeHome = Math.round((priceNum - ebayFee - paymentFee - shippingCost) * 100) / 100
    const netProfit = cogs.trim() !== '' ? Math.round((takeHome - cogsNum) * 100) / 100 : takeHome
    const marginPct = priceNum > 0 && cogs.trim() !== '' ? Math.round((netProfit / priceNum) * 100) : null
    const isNegativeMargin = netProfit < 0

    const handleApprove = async () => {
        if (!currentItem || isSubmitting) return
        tap()
        setIsSubmitting(true)
        try {
            // Save any pending edits
            await onUpdate(currentItem.id, {
                title: title.trim(),
                price: priceNum > 0 ? priceNum.toFixed(2) : undefined,
                condition: condition || undefined,
                cogs: cogs.trim() !== '' ? cogsNum : undefined,
            })
            await onApprove([currentItem.id])
            successHaptic()
            setApprovedCount(prev => prev + 1)
            setSessionNetProfit(prev => prev + Math.max(0, netProfit))
        } catch (err) {
            errorHaptic()
            console.error('Approval failed', err)
        } finally {
            setIsSubmitting(false)
        }
    }

    const handleDelete = async () => {
        if (!currentItem || isSubmitting) return
        warning()
        setIsSubmitting(true)
        try {
            await onDelete(currentItem.id)
        } catch (err) {
            errorHaptic()
            console.error('Delete failed', err)
        } finally {
            setIsSubmitting(false)
        }
    }

    const adjustPrice = (delta: number) => {
        tap()
        const next = Math.max(0.99, priceNum + delta)
        setPrice(next.toFixed(2))
    }

    const roundTo99 = () => {
        tap()
        const whole = Math.floor(priceNum)
        const next = whole + 0.99
        setPrice(next.toFixed(2))
    }

    return (
        <div className="w-full max-w-lg mx-auto space-y-4 pb-20">
            {/* Header / Deck Controls */}
            <div className="flex items-center justify-between px-1">
                <div className="flex items-center gap-2">
                    <span className="px-3 py-1 rounded-full bg-persimmon-100 text-persimmon-800 text-xs font-bold uppercase tracking-wider">
                        {currentIndex + 1} of {listings.length}
                    </span>
                    <span className="text-xs font-medium text-stone-400">5-Second Review Deck</span>
                </div>
                {onSwitchToList && (
                    <button
                        onClick={onSwitchToList}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-stone-500 hover:text-ink-800 px-2.5 py-1.5 rounded-lg hover:bg-stone-100 transition-colors"
                    >
                        <ListFilter size={14} />
                        List View
                    </button>
                )}
            </div>

            {/* Swipeable / Spring Review Card */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={currentItem.id}
                    initial={{ opacity: 0, y: 15, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, x: -60, scale: 0.95 }}
                    transition={{ type: 'spring', damping: 24, stiffness: 280 }}
                    className="bg-paper-card border border-stone-200/80 shadow-md rounded-3xl overflow-hidden flex flex-col"
                >
                    {/* Media Header with Badge Overlay */}
                    <div className="relative aspect-[4/3] bg-stone-100 overflow-hidden">
                        {currentItem.thumbnail_url ? (
                            <img
                                src={currentItem.thumbnail_url}
                                alt={title}
                                className="w-full h-full object-cover"
                            />
                        ) : (
                            <div className="w-full h-full flex flex-col items-center justify-center text-stone-400 gap-2">
                                <AlertCircle size={32} />
                                <span className="text-xs font-medium">No Thumbnail Available</span>
                            </div>
                        )}

                        {/* Top Overlay Badges */}
                        <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none">
                            <Badge className="bg-black/60 backdrop-blur-md text-white border-0 text-xs font-semibold px-2.5 py-1">
                                {currentItem.condition || 'Used'}
                            </Badge>
                            {currentItem.confidence_score !== undefined && currentItem.confidence_score !== null && (
                                <Badge className={cn(
                                    "backdrop-blur-md border-0 text-xs font-bold px-2.5 py-1 flex items-center gap-1",
                                    currentItem.confidence_score >= 0.85
                                        ? "bg-sage-600/90 text-white"
                                        : "bg-amber-600/90 text-white"
                                )}>
                                    {currentItem.confidence_score >= 0.85 ? <ShieldCheck size={12} /> : <ShieldAlert size={12} />}
                                    {Math.round(currentItem.confidence_score * 100)}% Match
                                </Badge>
                            )}
                        </div>

                        {/* Seller Note Banner (if present) */}
                        {currentItem.note && (
                            <div className="absolute bottom-0 inset-x-0 bg-amber-950/80 backdrop-blur-md text-amber-200 text-xs px-3.5 py-2 font-medium flex items-center gap-2 border-t border-amber-500/20">
                                <Tag size={13} className="shrink-0 text-amber-400" />
                                <span className="truncate">Seller Note: <strong>{currentItem.note}</strong></span>
                            </div>
                        )}
                    </div>

                    {/* Card Body */}
                    <div className="p-4 sm:p-5 space-y-4">
                        {/* Title Input */}
                        <div className="space-y-1">
                            <div className="flex justify-between items-center text-[11px] font-bold text-stone-400 uppercase tracking-wider">
                                <label htmlFor="card-title">Title</label>
                                <span className={title.length >= 80 ? 'text-red-500' : 'text-stone-400'}>
                                    {title.length}/80
                                </span>
                            </div>
                            <Input
                                id="card-title"
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                maxLength={80}
                                className="bg-stone-50/80 font-semibold text-sm h-11 border-stone-200 rounded-xl"
                                placeholder="Listing title..."
                            />
                        </div>

                        {/* Cassini SEO Scorecard & Quick Aspect Chips */}
                        {(() => {
                            const specifics = (currentItem.item_specifics || {}) as Record<string, string>
                            const aiData = (currentItem.ai_data || {}) as Record<string, any>
                            const seoMetrics = aiData.seo_metrics || {
                                seo_score: Math.min(100, Math.max(30, Object.keys(specifics).filter(k => specifics[k] && specifics[k] !== 'Does Not Apply').length * 10)),
                                total_aspects_count: Object.keys(specifics).filter(k => specifics[k] && specifics[k] !== 'Does Not Apply').length
                            }
                            const validEntries = Object.entries(specifics).filter(([_, v]) => v && v !== 'Does Not Apply' && String(v).trim())

                            return (
                                <div className="p-3 bg-stone-50/90 border border-stone-200/80 rounded-2xl space-y-2">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-1.5">
                                            <span className="text-xs">🎯</span>
                                            <span className="text-xs font-bold text-ink-800">Cassini SEO Fill Rate</span>
                                        </div>
                                        <Badge className={cn(
                                            "text-[10px] font-extrabold border-0 px-2 py-0.5",
                                            (seoMetrics.seo_score ?? 85) >= 80
                                                ? "bg-sage-600 text-white"
                                                : (seoMetrics.seo_score ?? 85) >= 60
                                                    ? "bg-amber-500 text-white"
                                                    : "bg-rose-500 text-white"
                                        )}>
                                            {seoMetrics.seo_score ?? 85}% · {validEntries.length} Specs Filled
                                        </Badge>
                                    </div>

                                    {validEntries.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5 pt-0.5">
                                            {validEntries.slice(0, 4).map(([k, v]) => (
                                                <span key={k} className="inline-flex items-center text-[10px] bg-white border border-stone-200 px-2 py-0.5 rounded-md font-medium text-stone-700 shadow-2xs">
                                                    <strong className="font-semibold text-ink-800 mr-1">{k}:</strong> {String(v)}
                                                </span>
                                            ))}
                                            {onOpenFullDetail && (
                                                <button
                                                    type="button"
                                                    onClick={() => onOpenFullDetail(currentItem)}
                                                    className="inline-flex items-center text-[10px] text-persimmon-700 hover:underline font-bold px-1"
                                                >
                                                    + View all ({validEntries.length}) →
                                                </button>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )
                        })()}

                        {/* Condition Fast Selector */}
                        <div className="space-y-1.5">
                            <span className="text-[11px] font-bold text-stone-400 uppercase tracking-wider block">
                                Condition
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                                {CONDITIONS.map(c => (
                                    <button
                                        key={c.value}
                                        type="button"
                                        onClick={() => {
                                            tap()
                                            setCondition(c.value)
                                        }}
                                        className={cn(
                                            "text-xs px-3 py-1.5 rounded-full font-medium transition-colors border",
                                            condition === c.value
                                                ? "bg-persimmon-600 text-white border-persimmon-500 shadow-xs"
                                                : "bg-stone-100/80 text-stone-600 border-stone-200 hover:bg-stone-200/60"
                                        )}
                                    >
                                        {c.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Price & COGS Station */}
                        <div className="grid grid-cols-2 gap-3 pt-1">
                            <div className="space-y-1">
                                <label className="text-[11px] font-bold text-stone-400 uppercase tracking-wider block">
                                    List Price
                                </label>
                                <div className="relative">
                                    <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400 font-bold text-sm">$</span>
                                    <Input
                                        value={price}
                                        onChange={(e) => setPrice(e.target.value)}
                                        inputMode="decimal"
                                        className="pl-7 bg-stone-50/80 font-bold text-base h-11 border-stone-200 rounded-xl"
                                    />
                                </div>
                                <div className="flex gap-1 pt-1">
                                    <button
                                        type="button"
                                        onClick={() => adjustPrice(-2)}
                                        className="flex-1 py-1 text-[10px] font-bold rounded-lg bg-stone-100 text-stone-600 hover:bg-stone-200"
                                    >
                                        -$2
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => adjustPrice(+5)}
                                        className="flex-1 py-1 text-[10px] font-bold rounded-lg bg-stone-100 text-stone-600 hover:bg-stone-200"
                                    >
                                        +$5
                                    </button>
                                    <button
                                        type="button"
                                        onClick={roundTo99}
                                        className="flex-1 py-1 text-[10px] font-bold rounded-lg bg-stone-100 text-stone-600 hover:bg-stone-200"
                                    >
                                        .99
                                    </button>
                                </div>
                            </div>

                            <div className="space-y-1">
                                <label className="text-[11px] font-bold text-stone-400 uppercase tracking-wider block">
                                    COGS (Paid)
                                </label>
                                <div className="relative">
                                    <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400 font-bold text-sm">$</span>
                                    <Input
                                        placeholder="0.00"
                                        value={cogs}
                                        onChange={(e) => setCogs(e.target.value)}
                                        inputMode="decimal"
                                        className="pl-7 bg-stone-50/80 font-bold text-base h-11 border-stone-200 rounded-xl"
                                    />
                                </div>
                                <span className="text-[10px] text-stone-400 block pt-1 truncate">
                                    Purchase / acquisition cost
                                </span>
                            </div>
                        </div>

                        {/* Live Net Margin Breakdown Box */}
                        {priceNum > 0 && (
                            <div className={cn(
                                "p-3 rounded-2xl border text-xs font-mono transition-colors",
                                isNegativeMargin
                                    ? "bg-red-50/80 border-red-200 text-red-700"
                                    : "bg-emerald-50/80 border-emerald-200 text-emerald-800"
                            )}>
                                <div className="flex items-center justify-between font-bold text-sm mb-1">
                                    <span className="flex items-center gap-1.5">
                                        <TrendingUp size={15} />
                                        {cogs.trim() !== '' ? 'Expected Net Profit' : 'Take-Home'}
                                    </span>
                                    <span className="text-base font-extrabold">
                                        ${netProfit.toFixed(2)}
                                        {marginPct !== null && ` (${marginPct}% margin)`}
                                    </span>
                                </div>
                                <div className="text-[10px] text-stone-500 flex flex-wrap gap-x-2 pt-1 border-t border-emerald-200/50">
                                    <span>eBay fee: -${ebayFee.toFixed(2)}</span>
                                    <span>· Ship: -${shippingCost.toFixed(2)}</span>
                                    {cogs.trim() !== '' && <span>· COGS: -${cogsNum.toFixed(2)}</span>}
                                </div>
                            </div>
                        )}

                        {/* Shipping Preset Selector */}
                        <div className="space-y-1.5">
                            <span className="text-[11px] font-bold text-stone-400 uppercase tracking-wider block">
                                Shipping
                            </span>
                            <div className="grid grid-cols-4 gap-1.5">
                                {SHIPPING_PRESETS.map(s => (
                                    <button
                                        key={s.label}
                                        type="button"
                                        onClick={() => {
                                            tap()
                                            setShippingCost(s.cost)
                                        }}
                                        className={cn(
                                            "flex flex-col items-center justify-center p-2 rounded-xl text-center border transition-colors",
                                            shippingCost === s.cost
                                                ? "bg-stone-800 text-white border-stone-800"
                                                : "bg-stone-50 text-stone-600 border-stone-200 hover:bg-stone-100"
                                        )}
                                    >
                                        <span className="text-[10px] font-semibold truncate w-full">{s.label}</span>
                                        <span className="text-[11px] font-bold">${s.cost.toFixed(2)}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Action Bar */}
                    <div className="p-4 bg-stone-50 border-t border-stone-200/80 flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="icon"
                            onClick={handleDelete}
                            disabled={isSubmitting}
                            className="h-14 w-14 rounded-2xl border-stone-200 hover:bg-red-50 hover:text-red-600 hover:border-red-200 shrink-0"
                            aria-label="Delete listing"
                        >
                            <Trash2 size={20} />
                        </Button>

                        {onOpenFullDetail && (
                            <Button
                                variant="outline"
                                onClick={() => onOpenFullDetail(currentItem)}
                                disabled={isSubmitting}
                                className="h-14 px-4 rounded-2xl border-stone-200 font-semibold text-stone-700 hover:bg-stone-100 shrink-0"
                            >
                                <Edit3 size={18} />
                            </Button>
                        )}

                        <Button
                            onClick={handleApprove}
                            disabled={isSubmitting || priceNum <= 0}
                            className="h-14 flex-1 rounded-2xl text-base font-bold bg-persimmon-600 hover:bg-persimmon-700 text-white shadow-md flex items-center justify-center gap-2"
                        >
                            <CheckCircle size={20} />
                            <span>Approve & List Now</span>
                        </Button>
                    </div>
                </motion.div>
            </AnimatePresence>

            {/* Deck Navigation Footer */}
            <div className="flex items-center justify-between px-2 pt-1 text-xs text-stone-400">
                <button
                    disabled={currentIndex === 0}
                    onClick={() => {
                        tap()
                        setCurrentIndex(prev => Math.max(0, prev - 1))
                    }}
                    className="inline-flex items-center gap-1 hover:text-stone-700 disabled:opacity-30 min-h-[44px]"
                >
                    <ArrowLeft size={16} />
                    Previous
                </button>
                <span>Tap or swipe to review</span>
                <button
                    disabled={currentIndex >= listings.length - 1}
                    onClick={() => {
                        tap()
                        setCurrentIndex(prev => Math.min(listings.length - 1, prev + 1))
                    }}
                    className="inline-flex items-center gap-1 hover:text-stone-700 disabled:opacity-30 min-h-[44px]"
                >
                    Next
                    <ArrowRight size={16} />
                </button>
            </div>
        </div>
    )
}
