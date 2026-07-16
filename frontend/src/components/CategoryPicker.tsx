import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { CAPTURE_CATEGORIES } from '@/lib/categories'
import { useHaptics } from '@/hooks/useHaptics'

interface CategoryPickerProps {
    isOpen: boolean
    onClose: () => void
    onPick: (categoryId: string) => void
}

/**
 * Category-first capture front door: "What are you listing?" -> tap a card.
 * The pick drives the category-tuned condition picker in the capture sheet.
 * Bottom sheet on mobile, centered modal on desktop.
 */
export function CategoryPicker({ isOpen, onClose, onPick }: CategoryPickerProps) {
    const { tap } = useHaptics()
    if (!isOpen) return null

    return (
        <AnimatePresence>
            <motion.div
                // z-[60]: must clear the bottom nav (z-50), which sits LATER in the DOM
                // and would otherwise paint over the sheet's bottom row and steal taps.
                className="fixed inset-0 z-[60] flex items-end md:items-center md:justify-center"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            >
                <motion.div
                    className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm"
                    onClick={onClose}
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                />
                <motion.div
                    className="relative w-full md:max-w-md bg-paper rounded-t-3xl md:rounded-3xl p-5 pb-safe shadow-2xl"
                    initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
                    transition={{ type: 'spring', damping: 30, stiffness: 300 }}
                >
                    <div className="flex items-center justify-between mb-1">
                        <h3 className="font-display font-bold text-xl text-ink-800 tracking-tight">What are you listing?</h3>
                        <button
                            onClick={onClose}
                            aria-label="Close"
                            className="w-9 h-9 rounded-full flex items-center justify-center text-stone-500 hover:bg-stone-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500/50"
                        >
                            <X size={20} />
                        </button>
                    </div>
                    <p className="text-sm text-stone-500 mb-4">Pick a category — we handle the rest.</p>
                    <div className="grid grid-cols-2 gap-3">
                        {CAPTURE_CATEGORIES.map(cat => (
                            <button
                                key={cat.id}
                                onClick={() => { tap(); onPick(cat.id) }}
                                className={cn(
                                    'flex flex-col items-start gap-3 p-4 rounded-2xl bg-white border border-stone-200/80 transition active:scale-[0.98] hover:border-stone-300 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500/50',
                                    // Catch-all card rides alone on the last row — let it fill it.
                                    cat.id === 'other' && 'col-span-2 flex-row items-center'
                                )}
                            >
                                <span className={cn('w-11 h-11 rounded-xl flex items-center justify-center', cat.iconBg, cat.iconText)}>
                                    <cat.icon size={22} />
                                </span>
                                <span className="font-semibold text-ink-800">{cat.label}</span>
                            </button>
                        ))}
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    )
}
