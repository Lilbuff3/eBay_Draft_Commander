import { useRef, useState, useCallback } from 'react'
import { Plus, Camera, ImagePlus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useHaptics } from '@/hooks/useHaptics'
import { AnimatePresence, motion } from 'framer-motion'

interface MobileUploadFABProps {
    onFilesSelected: (files: FileList) => void
    className?: string
}

export function MobileUploadFAB({ onFilesSelected, className }: MobileUploadFABProps) {
    const cameraInputRef = useRef<HTMLInputElement>(null)
    const galleryInputRef = useRef<HTMLInputElement>(null)
    const [isExpanded, setIsExpanded] = useState(false)
    const { press, tap } = useHaptics()

    const toggleExpanded = useCallback(() => {
        press()
        setIsExpanded(prev => !prev)
    }, [press])

    const handleCamera = useCallback(() => {
        tap()
        cameraInputRef.current?.click()
        setIsExpanded(false)
    }, [tap])

    const handleGallery = useCallback(() => {
        tap()
        galleryInputRef.current?.click()
        setIsExpanded(false)
    }, [tap])

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            onFilesSelected(e.target.files)
            e.target.value = ''
        }
    }

    const handleScrimClick = useCallback(() => {
        setIsExpanded(false)
    }, [])

    return (
        <>
            {/* Scrim overlay */}
            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="fixed inset-0 z-30 fab-scrim md:hidden"
                        onClick={handleScrimClick}
                    />
                )}
            </AnimatePresence>

            {/* Speed dial container */}
            <div className={cn("fixed z-40 md:hidden bottom-20 right-4", className)}>
                {/* Mini FABs — Camera & Gallery */}
                <AnimatePresence>
                    {isExpanded && (
                        <>
                            {/* Gallery option */}
                            <motion.button
                                initial={{ opacity: 0, scale: 0.3, y: 20 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.3, y: 20 }}
                                transition={{ duration: 0.2, delay: 0.05 }}
                                type="button"
                                onClick={handleGallery}
                                className={cn(
                                    "absolute bottom-[136px] right-0",
                                    "w-12 h-12 rounded-2xl",
                                    "bg-white shadow-lg shadow-stone-900/15",
                                    "flex items-center justify-center",
                                    "active:scale-90 transition-transform",
                                )}
                                aria-label="Choose from gallery"
                            >
                                <ImagePlus size={22} className="text-sage-600" />
                            </motion.button>

                            {/* Gallery label */}
                            <motion.span
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 10 }}
                                transition={{ duration: 0.15, delay: 0.1 }}
                                className="absolute bottom-[146px] right-16 text-sm font-semibold text-white whitespace-nowrap bg-stone-800/80 px-3 py-1.5 rounded-lg"
                            >
                                Gallery
                            </motion.span>

                            {/* Camera option */}
                            <motion.button
                                initial={{ opacity: 0, scale: 0.3, y: 20 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.3, y: 20 }}
                                transition={{ duration: 0.2, delay: 0 }}
                                type="button"
                                onClick={handleCamera}
                                className={cn(
                                    "absolute bottom-[76px] right-0",
                                    "w-12 h-12 rounded-2xl",
                                    "bg-white shadow-lg shadow-stone-900/15",
                                    "flex items-center justify-center",
                                    "active:scale-90 transition-transform",
                                )}
                                aria-label="Take photo"
                            >
                                <Camera size={22} className="text-sage-600" />
                            </motion.button>

                            {/* Camera label */}
                            <motion.span
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 10 }}
                                transition={{ duration: 0.15, delay: 0.05 }}
                                className="absolute bottom-[86px] right-16 text-sm font-semibold text-white whitespace-nowrap bg-stone-800/80 px-3 py-1.5 rounded-lg"
                            >
                                Camera
                            </motion.span>
                        </>
                    )}
                </AnimatePresence>

                {/* Main FAB */}
                <button
                    type="button"
                    onClick={toggleExpanded}
                    className={cn(
                        'w-14 h-14 rounded-2xl',
                        'bg-gradient-to-br from-sage-500 to-sage-600',
                        'shadow-lg shadow-sage-500/30',
                        'flex items-center justify-center',
                        'active:scale-90 transition-all duration-200',
                    )}
                    aria-label={isExpanded ? "Close upload options" : "Add photos"}
                >
                    <motion.div
                        animate={{ rotate: isExpanded ? 45 : 0 }}
                        transition={{ duration: 0.2, ease: 'easeOut' }}
                    >
                        <Plus size={24} className="text-white" strokeWidth={2.5} />
                    </motion.div>
                </button>
            </div>

            {/* Hidden file inputs */}
            <input
                ref={cameraInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleChange}
                className="hidden"
            />
            <input
                ref={galleryInputRef}
                type="file"
                multiple
                accept="image/*"
                onChange={handleChange}
                className="hidden"
            />
        </>
    )
}
