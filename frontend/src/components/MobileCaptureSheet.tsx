import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Camera, Images, Trash2, Upload, Check, ChevronDown } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { useHaptics } from '@/hooks/useHaptics'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { getCaptureCategory, GENERIC_CONDITIONS } from '@/lib/categories'
import { useCommanderStore } from '@/store/useCommanderStore'
import { trackEvent } from '@/lib/api'

const genId = () => Math.random().toString(36).substring(7)

type CaptureMetadata = { title: string; condition: string; category?: string; cogs?: number }

interface MobileCaptureSheetProps {
    isOpen: boolean
    onClose: () => void
    initialFiles?: File[]
    /** category id from the picker (clothing/shoes/electronics/books) */
    category?: string
    /** reopen the category picker on top of the sheet */
    onChangeCategory?: () => void
    /** Returns job id when known so the session scoreboard can track list prices. */
    onUpload: (files: File[], metadata: CaptureMetadata) => Promise<string | void>
}

/** Session scoreboard entry — COGS is known at upload; list price arrives later via jobs store. */
type SessionItem = { jobId?: string; cogs: number }

export function MobileCaptureSheet({ isOpen, onClose, initialFiles = [], category, onChangeCategory, onUpload }: MobileCaptureSheetProps) {
    const captureCategory = getCaptureCategory(category)
    const conditions = captureCategory?.conditions ?? GENERIC_CONDITIONS
    const [photos, setPhotos] = useState<{ file: File; id: string; url: string }[]>([])
    const [title, setTitle] = useState('')
    const [condition, setCondition] = useState<string>('')
    const [cogs, setCogs] = useState<string>('')
    const [isUploading, setIsUploading] = useState(false)
    // The momentum loop: 'capture' is the form, 'success' is the interstitial
    // between items. sessionCount survives close/reopen on purpose — it's the
    // pile counter for the whole capture session, not one sheet-open.
    const [phase, setPhase] = useState<'capture' | 'success'>('capture')
    const [sessionCount, setSessionCount] = useState(0)
    const [sessionItems, setSessionItems] = useState<SessionItem[]>([])
    const { tap, press, success: successHaptic, warning, error: errorHaptic } = useHaptics()
    const fileInputRef = useRef<HTMLInputElement>(null)

    const uploadProgress = useCommanderStore(s => s.uploadProgress)
    const pct = uploadProgress && uploadProgress.total > 0
        ? Math.min(100, Math.round((uploadProgress.loaded / uploadProgress.total) * 100))
        : null

    // /api/jobs list carries price (not would_list_at / metadata_json). Match by
    // job id captured at upload so the scoreboard updates when AI finishes.
    const jobs = useCommanderStore(s => s.jobs)
    const sessionCogs = sessionItems.reduce((sum, item) => sum + item.cogs, 0)
    const sessionSales = sessionItems.reduce((sum, item) => {
        if (!item.jobId) return sum
        const job = jobs.find(j => j.id === item.jobId)
        const listPrice = parseFloat(job?.price || '0') || 0
        if (listPrice <= 0) return sum
        const fees = listPrice * 0.15 + 0.30
        const shipping = 6.50
        const net = listPrice - fees - shipping
        return sum + (net > 0 ? net : 0)
    }, 0)
    const sessionProfit = sessionSales - sessionCogs
    const showScoreboard = sessionItems.length > 0

    // Load initial files
    useEffect(() => {
        if (isOpen && initialFiles.length > 0) {
            const newPhotos = initialFiles.map(file => ({
                file,
                id: genId(),
                url: URL.createObjectURL(file)
            }))
            setPhotos(newPhotos)
        }
    }, [isOpen, initialFiles])

    // Cleanup object URLs when closed
    useEffect(() => {
        if (!isOpen) {
            photos.forEach(p => URL.revokeObjectURL(p.url))
            setPhotos([])
            setTitle('')
            setCondition('')
            setCogs('')
            setIsUploading(false)
            setPhase('capture')
        }
    }, [isOpen]) // eslint-disable-line react-hooks/exhaustive-deps

    // Category switched mid-session: keep the condition only if the new
    // category's condition set still contains it (values differ per vertical).
    useEffect(() => {
        setCondition(prev => (prev && !conditions.some(c => c.value === prev) ? '' : prev))
    }, [captureCategory]) // eslint-disable-line react-hooks/exhaustive-deps

    const galleryInputRef = useRef<HTMLInputElement>(null)

    const handleTakePhoto = () => {
        tap()
        fileInputRef.current?.click()
    }

    const handlePickFromGallery = () => {
        tap()
        galleryInputRef.current?.click()
    }

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            const newFiles = Array.from(e.target.files).map(file => ({
                file,
                id: genId(),
                url: URL.createObjectURL(file)
            }))
            setPhotos(prev => [...prev, ...newFiles])
            e.target.value = ''
        }
    }

    const handleDelete = (id: string, url: string) => {
        warning()
        URL.revokeObjectURL(url)
        setPhotos(prev => prev.filter(p => p.id !== id))
    }

    const handleSubmit = async () => {
        if (photos.length === 0) return
        tap()
        setIsUploading(true)
        try {
            const metadataPayload: CaptureMetadata = { title, condition, category }
            const cogsVal = cogs.trim() !== '' ? parseFloat(cogs) : NaN
            if (!Number.isNaN(cogsVal) && cogsVal >= 0) {
                metadataPayload.cogs = cogsVal
            }

            const jobId = await onUpload(
                photos.map(p => p.file),
                metadataPayload
            )

            setSessionItems(prev => [
                ...prev,
                { jobId: jobId || undefined, cogs: metadataPayload.cogs ?? 0 },
            ])
            
            trackEvent('capture_success', { 
                category, 
                has_title: !!title, 
                has_condition: !!condition, 
                photo_count: photos.length,
                session_count: sessionCount + 1
            })

            // Momentum, not a dead end: clear the item but keep the sheet (and
            // the sticky condition — piles are usually same-condition) and land
            // on the success interstitial with a one-tap path to the next item.
            successHaptic()
            photos.forEach(p => URL.revokeObjectURL(p.url))
            setPhotos([])
            setTitle('')
            setCogs('')
            setIsUploading(false)
            setSessionCount(n => n + 1)
            setPhase('success')
        } catch (err) {
            // Never fail silently here — this is the app's core action, and the
            // sheet stays open with the photos intact so the tap can be retried.
            console.error(err)
            trackEvent('capture_error', { error: err instanceof Error ? err.message : String(err) })
            errorHaptic()
            toast.error('Upload failed', {
                description: err instanceof Error ? err.message : 'Your photos are still here — tap Upload to retry.',
            })
            setIsUploading(false)
        }
    }

    // One tap from "item sent" to shooting the next one: reset the phase and
    // fire the camera input in the same gesture.
    const handleNextItem = () => {
        trackEvent('momentum_loop_next', { session_count: sessionCount })
        press()
        setPhase('capture')
        fileInputRef.current?.click()
    }
    
    const handleDoneForNow = () => {
        trackEvent('momentum_loop_done', { session_count: sessionCount })
        tap()
        onClose()
    }

    return (
        <AnimatePresence>
            {isOpen && (
            <motion.div
                key="capture-sheet"
                initial={{ opacity: 0, y: 100 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 100 }}
                transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                // z-[60]: clears the bottom nav (z-50, later in DOM) which otherwise
                // paints over the footer CTA and intercepts its taps.
                className="fixed inset-0 z-[60] flex flex-col bg-stone-50"
            >
                {/* Header */}
                <header className="flex items-center justify-between px-4 py-3 bg-white border-b border-stone-200">
                    <div className="min-w-0">
                        <h2 className="text-xl font-bold tracking-tight text-stone-800">New Listing</h2>
                        {captureCategory && onChangeCategory && phase === 'capture' && (
                            <button
                                onClick={() => { tap(); onChangeCategory() }}
                                className="mt-0.5 inline-flex items-center gap-1 text-xs font-medium text-persimmon-600 active:text-persimmon-700"
                            >
                                <captureCategory.icon size={12} />
                                {captureCategory.label}
                                <ChevronDown size={12} />
                            </button>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        {sessionCount > 0 && (
                            <span className="px-2.5 py-1 rounded-full bg-sage-100 text-sage-700 text-xs font-bold">
                                {sessionCount} sent
                            </span>
                        )}
                        <button
                            onClick={onClose}
                            disabled={isUploading}
                            title="Close"
                            aria-label="Close"
                            className="w-11 h-11 grid place-items-center rounded-full hover:bg-stone-100 disabled:opacity-50"
                        >
                            <X size={24} className="text-stone-500" />
                        </button>
                    </div>
                </header>

                {/* Session Scoreboard — COGS from this sheet session; sales/profit update when job.price arrives */}
                {showScoreboard && (
                    <div className="bg-stone-50 px-4 py-3 border-b border-stone-200 flex items-center justify-between shadow-sm z-10 relative">
                        <div className="flex flex-col">
                            <span className="text-[10px] font-bold text-stone-400 uppercase tracking-wider">Total Spent</span>
                            <span className="text-sm font-semibold text-stone-700">${sessionCogs.toFixed(2)}</span>
                        </div>
                        <div className="flex flex-col text-center">
                            <span className="text-[10px] font-bold text-stone-400 uppercase tracking-wider">Expected Net</span>
                            <span className="text-sm font-semibold text-stone-700">
                                {sessionSales > 0 ? `$${sessionSales.toFixed(2)}` : '—'}
                            </span>
                        </div>
                        <div className="flex flex-col text-right">
                            <span className="text-[10px] font-bold text-stone-400 uppercase tracking-wider">Expected Profit</span>
                            <span className={cn("text-base font-bold", sessionProfit > 0 ? "text-sage-600" : "text-stone-700")}>
                                {sessionSales > 0
                                    ? `${sessionProfit > 0 ? '+' : ''}$${sessionProfit.toFixed(2)}`
                                    : '—'}
                            </span>
                        </div>
                    </div>
                )}

                {phase === 'success' ? (
                    /* Success interstitial — the Vendit-style momentum beat. AI runs in
                       the background; the only job here is getting to the next item. */
                    <>
                        <div className="flex-1 flex flex-col items-center justify-center gap-5 px-8 text-center">
                            <motion.div
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                transition={{ type: 'spring', damping: 12, stiffness: 250, delay: 0.05 }}
                                className="w-20 h-20 rounded-full bg-sage-100 grid place-items-center"
                            >
                                <Check size={40} className="text-sage-600" strokeWidth={3} />
                            </motion.div>
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.15 }}
                                className="space-y-1.5"
                            >
                                <div className="font-bold text-2xl tracking-tight text-stone-800">
                                    Item #{sessionCount} on its way
                                </div>
                                <p className="text-sm text-stone-500">
                                    AI is researching and building the listing — keep the pile moving.
                                </p>
                            </motion.div>
                        </div>
                        <div className="fixed bottom-0 left-0 right-0 p-4 pb-safe bg-white border-t border-stone-200 space-y-2">
                            <Button
                                onClick={handleNextItem}
                                className="w-full h-14 rounded-2xl text-base font-semibold shadow-md bg-persimmon-600 hover:bg-persimmon-700"
                            >
                                <span className="flex items-center gap-2">
                                    <Camera size={20} />
                                    Snap next item
                                </span>
                            </Button>
                            <Button
                                onClick={handleDoneForNow}
                                variant="ghost"
                                className="w-full h-11 rounded-2xl text-sm font-medium text-stone-500"
                            >
                                Done for now
                            </Button>
                        </div>
                    </>
                ) : (
                <>
                <div className="flex-1 overflow-y-auto w-full pb-safe p-4 pb-24 space-y-6">
                    {/* Photo Grid */}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <h3 className="font-semibold text-stone-800 flex items-center gap-2">
                                <Camera size={18} className="text-persimmon-600" />
                                Photos <span className="text-stone-500 font-normal">({photos.length})</span>
                            </h3>
                            {photos.length > 0 && (
                                <div className="flex items-center gap-1">
                                    <button onClick={handleTakePhoto} className="inline-flex items-center gap-1.5 text-sm font-medium text-persimmon-600 px-3 min-h-[44px] rounded-lg hover:bg-persimmon-50">
                                        <Camera size={16} /> Camera
                                    </button>
                                    <button onClick={handlePickFromGallery} className="inline-flex items-center gap-1.5 text-sm font-medium text-persimmon-600 px-3 min-h-[44px] rounded-lg hover:bg-persimmon-50">
                                        <Images size={16} /> Gallery
                                    </button>
                                </div>
                            )}
                        </div>

                        <div className="grid grid-cols-3 gap-3">
                            <AnimatePresence mode="popLayout" initial={false}>
                                {photos.map((photo, index) => (
                                    <motion.div
                                        key={photo.id}
                                        layout
                                        initial={{ opacity: 0, scale: 0.8 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        exit={{ opacity: 0, scale: 0.8 }}
                                        transition={{ type: 'spring', damping: 22, stiffness: 300 }}
                                        className="relative aspect-square rounded-xl overflow-hidden bg-stone-200 shadow-sm outline outline-1 outline-stone-200"
                                    >
                                        <img src={photo.url} alt={`Preview ${index}`} className="w-full h-full object-cover" />
                                        <button
                                            type="button"
                                            title="Delete photo"
                                            aria-label="Delete photo"
                                            onClick={() => handleDelete(photo.id, photo.url)}
                                            className="absolute top-1 right-1 p-1.5 rounded-full bg-black/50 text-white backdrop-blur-sm active:scale-90 transition-transform"
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                            {photos.length === 0 ? (
                                /* Empty state: both capture routes, side by side. The camera is
                                   the fast path; gallery reaches photos already taken (and
                                   multi-selects — capture inputs can't). */
                                <div className="col-span-3 grid grid-cols-2 gap-3">
                                    <button
                                        onClick={handleTakePhoto}
                                        className="aspect-[3/2] rounded-xl border-2 border-dashed border-persimmon-300 bg-persimmon-50 flex flex-col items-center justify-center gap-1.5 text-persimmon-700 active:bg-persimmon-100 transition-colors"
                                    >
                                        <Camera size={26} />
                                        <span className="font-medium text-sm">Take photos</span>
                                    </button>
                                    <button
                                        onClick={handlePickFromGallery}
                                        className="aspect-[3/2] rounded-xl border-2 border-dashed border-stone-300 bg-stone-100 flex flex-col items-center justify-center gap-1.5 text-stone-600 active:bg-stone-200 transition-colors"
                                    >
                                        <Images size={26} />
                                        <span className="font-medium text-sm">From gallery</span>
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={handleTakePhoto}
                                    aria-label="Take another photo"
                                    className="aspect-square rounded-xl border-2 border-dashed border-stone-300 bg-stone-100 flex flex-col items-center justify-center gap-1 text-stone-500 active:bg-stone-200 active:border-stone-400 transition-colors"
                                >
                                    <Camera size={24} />
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Metadata Section */}
                    {photos.length > 0 && (
                        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
                            <div className="space-y-2">
                                <label className="text-sm font-semibold text-stone-700">Item Name (Optional)</label>
                                <Input
                                    placeholder="Leave blank for AI to suggest"
                                    value={title}
                                    onChange={(e) => setTitle(e.target.value)}
                                    className="bg-white h-12"
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-semibold text-stone-700">
                                    Condition{captureCategory ? ` · ${captureCategory.label}` : ' (Optional)'}
                                </label>
                                <div className="flex flex-wrap gap-2">
                                    {conditions.map((cond) => (
                                        <button
                                            key={cond.value}
                                            onClick={() => {
                                                tap()
                                                setCondition(cond.value === condition ? '' : cond.value)
                                            }}
                                            className={cn(
                                                "px-4 py-2 rounded-full text-sm font-medium border transition-colors",
                                                condition === cond.value
                                                    ? "bg-persimmon-600 text-white border-persimmon-500"
                                                    : "bg-white text-stone-600 border-stone-200 hover:border-stone-300"
                                            )}
                                        >
                                            {cond.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            
                            <div className="space-y-2">
                                <label className="text-sm font-semibold text-stone-700">Cost of Goods (COGS)</label>
                                <div className="relative">
                                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-stone-500 font-medium">$</span>
                                    <Input
                                        type="number"
                                        placeholder="0.00"
                                        value={cogs}
                                        onChange={(e) => setCogs(e.target.value)}
                                        className="bg-white h-12 pl-8 font-medium"
                                        step="0.01"
                                        min="0"
                                    />
                                </div>
                            </div>
                        </motion.div>
                    )}
                </div>

                {/* Footer fixed */}
                <div className="fixed bottom-0 left-0 right-0 p-4 pb-safe bg-white border-t border-stone-200">
                    <Button
                        onClick={handleSubmit}
                        disabled={photos.length === 0 || isUploading}
                        className="relative overflow-hidden w-full h-14 rounded-2xl text-base font-semibold shadow-md bg-persimmon-600 hover:bg-persimmon-700"
                    >
                        {/* Progress fill behind the label while the upload streams */}
                        {isUploading && pct !== null && (
                            <span
                                aria-hidden
                                className="absolute inset-y-0 left-0 bg-white/25 transition-[width] duration-200 ease-out"
                                style={{ width: `${pct}%` }}
                            />
                        )}
                        {isUploading ? (
                            <span className="relative">{pct === null ? 'Uploading…' : `Uploading… ${pct}%`}</span>
                        ) : (
                            <span className="relative flex items-center gap-2">
                                <Upload size={20} />
                                Upload & List ({photos.length})
                            </span>
                        )}
                    </Button>
                </div>
                </>
                )}

                {/* Two hidden inputs: `capture` forces the OS camera and silently
                    ignores `multiple`, so gallery multi-select needs its own input.
                    They live outside the phase switch so "Snap next item" can fire
                    the camera from the success screen. */}
                <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    title="Camera input"
                    aria-label="Camera input"
                    className="hidden"
                    onChange={handleFileChange}
                />
                <input
                    ref={galleryInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    title="Gallery input"
                    aria-label="Gallery input"
                    className="hidden"
                    onChange={handleFileChange}
                />
            </motion.div>
            )}
        </AnimatePresence>
    )
}
