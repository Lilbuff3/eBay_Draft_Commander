import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Camera, Images, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { useHaptics } from '@/hooks/useHaptics'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { getCaptureCategory, GENERIC_CONDITIONS } from '@/lib/categories'
import { useCommanderStore } from '@/store/useCommanderStore'

const genId = () => Math.random().toString(36).substring(7)

interface MobileCaptureSheetProps {
    isOpen: boolean
    onClose: () => void
    initialFiles?: File[]
    /** category id from the picker (clothing/shoes/electronics/books) */
    category?: string
    onUpload: (files: File[], metadata: { title: string; condition: string; category?: string }) => Promise<void>
}

export function MobileCaptureSheet({ isOpen, onClose, initialFiles = [], category, onUpload }: MobileCaptureSheetProps) {
    const captureCategory = getCaptureCategory(category)
    const conditions = captureCategory?.conditions ?? GENERIC_CONDITIONS
    const [photos, setPhotos] = useState<{ file: File; id: string; url: string }[]>([])
    const [title, setTitle] = useState('')
    const [condition, setCondition] = useState<string>('')
    const [isUploading, setIsUploading] = useState(false)
    const { tap, warning, error: errorHaptic } = useHaptics()
    const fileInputRef = useRef<HTMLInputElement>(null)

    const uploadProgress = useCommanderStore(s => s.uploadProgress)
    const pct = uploadProgress && uploadProgress.total > 0
        ? Math.min(100, Math.round((uploadProgress.loaded / uploadProgress.total) * 100))
        : null

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
            setIsUploading(false)
        }
    }, [isOpen]) // eslint-disable-line react-hooks/exhaustive-deps

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
            await onUpload(
                photos.map(p => p.file),
                { title, condition, category }
            )
            onClose()
        } catch (err) {
            // Never fail silently here — this is the app's core action, and the
            // sheet stays open with the photos intact so the tap can be retried.
            console.error(err)
            errorHaptic()
            toast.error('Upload failed', {
                description: err instanceof Error ? err.message : 'Your photos are still here — tap Upload to retry.',
            })
            setIsUploading(false)
        }
    }

    if (!isOpen) return null

    return (
        <AnimatePresence>
            <motion.div
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
                    <h2 className="text-xl font-bold tracking-tight text-stone-800">New Listing</h2>
                    <button
                        onClick={onClose}
                        disabled={isUploading}
                        title="Close"
                        aria-label="Close"
                        className="w-11 h-11 grid place-items-center rounded-full hover:bg-stone-100 disabled:opacity-50"
                    >
                        <X size={24} className="text-stone-500" />
                    </button>
                </header>

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
                            {photos.map((photo, index) => (
                                <div key={photo.id} className="relative aspect-square rounded-xl overflow-hidden bg-stone-200 shadow-sm outline outline-1 outline-stone-200">
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
                                </div>
                            ))}
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
                        </motion.div>
                    )}
                </div>

                {/* Footer fixed */}
                <div className="fixed bottom-0 left-0 right-0 p-4 pb-safe bg-white border-t border-stone-200">
                    <Button 
                        onClick={handleSubmit} 
                        disabled={photos.length === 0 || isUploading}
                        className="w-full h-14 rounded-2xl text-base font-semibold shadow-md bg-persimmon-600 hover:bg-persimmon-700"
                    >
                        {isUploading ? (
                            <span>{pct === null ? 'Uploading…' : `Uploading… ${pct}%`}</span>
                        ) : (
                            <span className="flex items-center gap-2">
                                <Upload size={20} />
                                Upload & List ({photos.length})
                            </span>
                        )}
                    </Button>
                </div>
                
                {/* Two hidden inputs: `capture` forces the OS camera and silently
                    ignores `multiple`, so gallery multi-select needs its own input. */}
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
        </AnimatePresence>
    )
}
