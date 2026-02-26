import { useRef } from 'react'
import { Plus } from 'lucide-react'
import { cn } from '@/lib/utils'

interface MobileUploadFABProps {
    onFilesSelected: (files: FileList) => void
    className?: string
}

export function MobileUploadFAB({ onFilesSelected, className }: MobileUploadFABProps) {
    const inputRef = useRef<HTMLInputElement>(null)

    const handleClick = () => {
        inputRef.current?.click()
    }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            onFilesSelected(e.target.files)
            // Reset so same file can be selected again
            e.target.value = ''
        }
    }

    return (
        <>
            <button
                type="button"
                onClick={handleClick}
                className={cn(
                    'fixed z-40 md:hidden',
                    'bottom-20 right-4',
                    'w-14 h-14 rounded-full',
                    'bg-gradient-to-br from-sage-500 to-sage-600',
                    'shadow-lg shadow-sage-500/30',
                    'flex items-center justify-center',
                    'active:scale-95 transition-transform',
                    className,
                )}
                aria-label="Add photos"
            >
                <Plus size={24} className="text-white" strokeWidth={2.5} />
            </button>
            <input
                ref={inputRef}
                type="file"
                multiple
                accept="image/*"
                onChange={handleChange}
                className="hidden"
            />
        </>
    )
}
