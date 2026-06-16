import { useState, useCallback } from 'react'
import { Plus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useHaptics } from '@/hooks/useHaptics'
import { motion } from 'framer-motion'
import { CategoryPicker } from './CategoryPicker'
import { MobileCaptureSheet } from './MobileCaptureSheet'
import { useCommanderStore } from '@/store/useCommanderStore'
import { uploadFiles } from '@/lib/api'

interface MobileUploadFABProps {
    onUploadComplete: (jobId: string) => void
    className?: string
}

export function MobileUploadFAB({ onUploadComplete, className }: MobileUploadFABProps) {
    const [isCategoryOpen, setIsCategoryOpen] = useState(false)
    const [isCaptureSheetOpen, setIsCaptureSheetOpen] = useState(false)
    const [category, setCategory] = useState<string | undefined>(undefined)
    const { press, tap } = useHaptics()

    const openPicker = useCallback(() => {
        press()
        setIsCategoryOpen(true)
    }, [press])

    const handlePick = useCallback((categoryId: string) => {
        tap()
        setCategory(categoryId)
        setIsCategoryOpen(false)
        setIsCaptureSheetOpen(true)
    }, [tap])

    return (
        <>
            {/* Main FAB — opens the category-first picker */}
            <div className={cn('fixed z-40 md:hidden bottom-20 right-4', className)}>
                <button
                    type="button"
                    onClick={openPicker}
                    className={cn(
                        'w-14 h-14 rounded-2xl bg-persimmon-500 shadow-lg shadow-persimmon-500/30',
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

            <CategoryPicker
                isOpen={isCategoryOpen}
                onClose={() => setIsCategoryOpen(false)}
                onPick={handlePick}
            />

            <MobileCaptureSheet
                isOpen={isCaptureSheetOpen}
                onClose={() => setIsCaptureSheetOpen(false)}
                category={category}
                onUpload={async (files, metadata) => {
                    const setProgress = useCommanderStore.getState().setUploadProgress
                    setProgress({ loaded: 0, total: 1, fileCount: files.length })
                    try {
                        const res = await uploadFiles(files, (loaded, total) => {
                            setProgress({ loaded, total, fileCount: files.length })
                        }, metadata)
                        const newJobId = res.jobId || res.job_id
                        if (newJobId) {
                            onUploadComplete(newJobId)
                        }
                    } finally {
                        setProgress(null)
                    }
                }}
            />
        </>
    )
}
