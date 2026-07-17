import { useState, useCallback } from 'react'
import { Plus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useHaptics } from '@/hooks/useHaptics'
import { motion } from 'framer-motion'
import { CategoryPicker } from './CategoryPicker'
import { MobileCaptureSheet } from './MobileCaptureSheet'
import { getCaptureCategory } from '@/lib/categories'
import { useCommanderStore } from '@/store/useCommanderStore'
import { uploadFiles } from '@/lib/api'

interface MobileUploadFABProps {
    onUploadComplete: (jobId: string) => void
    className?: string
}

// Sticky category: piles are usually one vertical, so repeat captures skip the
// picker entirely (FAB → camera). The sheet header shows the category with a
// one-tap Change that reopens the picker.
const LAST_CATEGORY_KEY = 'dc-capture-category'

function loadLastCategory(): string | undefined {
    try {
        const stored = localStorage.getItem(LAST_CATEGORY_KEY)
        return getCaptureCategory(stored) ? stored ?? undefined : undefined
    } catch {
        return undefined
    }
}

export function MobileUploadFAB({ onUploadComplete, className }: MobileUploadFABProps) {
    const [isCategoryOpen, setIsCategoryOpen] = useState(false)
    const [isCaptureSheetOpen, setIsCaptureSheetOpen] = useState(false)
    const [category, setCategory] = useState<string | undefined>(loadLastCategory)
    const { press, tap } = useHaptics()

    const openCapture = useCallback(() => {
        press()
        // Known category from a previous capture → straight to the sheet.
        if (getCaptureCategory(category)) setIsCaptureSheetOpen(true)
        else setIsCategoryOpen(true)
    }, [press, category])

    const handlePick = useCallback((categoryId: string) => {
        tap()
        setCategory(categoryId)
        try { localStorage.setItem(LAST_CATEGORY_KEY, categoryId) } catch { /* private mode */ }
        setIsCategoryOpen(false)
        setIsCaptureSheetOpen(true)
    }, [tap])

    return (
        <>
            {/* Main FAB — sticky category goes straight to capture; first run picks */}
            <div className={cn('fixed z-40 md:hidden bottom-20 right-4', className)}>
                <button
                    type="button"
                    onClick={openCapture}
                    className={cn(
                        'w-14 h-14 rounded-2xl bg-persimmon-600 shadow-lg shadow-persimmon-600/30',
                        'flex items-center justify-center active:scale-90 transition duration-200',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper',
                    )}
                    aria-label="Add an item"
                >
                    <motion.div animate={{ rotate: isCategoryOpen ? 45 : 0 }} transition={{ duration: 0.2, ease: 'easeOut' }}>
                        <Plus size={24} className="text-white" strokeWidth={2.5} />
                    </motion.div>
                </button>
            </div>

            <MobileCaptureSheet
                isOpen={isCaptureSheetOpen}
                onClose={() => setIsCaptureSheetOpen(false)}
                category={category}
                onChangeCategory={() => setIsCategoryOpen(true)}
                onUpload={async (files, metadata) => {
                    const setProgress = useCommanderStore.getState().setUploadProgress
                    setProgress({ loaded: 0, total: 1, fileCount: files.length })
                    try {
                        // silent: the sheet's success interstitial + error toast own
                        // all feedback for this path — api-level toasts would double up.
                        const res = await uploadFiles(files, (loaded, total) => {
                            setProgress({ loaded, total, fileCount: files.length })
                        }, metadata, { silent: true })
                        const newJobId = res.jobId || res.job_id
                        if (newJobId) {
                            onUploadComplete(newJobId)
                        }
                    } finally {
                        setProgress(null)
                    }
                }}
            />

            {/* After the sheet in the DOM: same z-index, so the picker paints on
                top when opened from the sheet's Change button. */}
            <CategoryPicker
                isOpen={isCategoryOpen}
                onClose={() => setIsCategoryOpen(false)}
                onPick={handlePick}
            />
        </>
    )
}
