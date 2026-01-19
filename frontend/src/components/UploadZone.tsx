import { useState, useCallback } from 'react'
import { Upload, X, Loader2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

interface UploadZoneProps {
    onUploadComplete?: (jobId: string) => void
}

export function UploadZone({ onUploadComplete }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false)
    const [isUploading, setIsUploading] = useState(false)
    const [uploadStatus, setUploadStatus] = useState<{ success: boolean; message: string } | null>(null)

    const handleDrop = useCallback(async (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)

        const files = Array.from(e.dataTransfer.files).filter(f =>
            f.type.startsWith('image/')
        )

        if (files.length === 0) {
            setUploadStatus({ success: false, message: 'No image files found' })
            return
        }

        await uploadFiles(files)
    }, [])

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files
        if (!files || files.length === 0) return
        await uploadFiles(Array.from(files))
    }

    const uploadFiles = async (files: File[]) => {
        setIsUploading(true)
        setUploadStatus(null)

        const formData = new FormData()
        files.forEach(file => formData.append('files[]', file))

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            })
            const data = await res.json()

            if (data.success) {
                setUploadStatus({ success: true, message: data.message })
                onUploadComplete?.(data.jobId)
            } else {
                setUploadStatus({ success: false, message: data.error || 'Upload failed' })
            }
        } catch (err) {
            setUploadStatus({ success: false, message: 'Network error' })
        } finally {
            setIsUploading(false)
        }
    }

    return (
        <div className="relative">
            <motion.div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                animate={{
                    scale: isDragging ? 1.02 : 1,
                    borderColor: isDragging ? '#84A98C' : '#e7e5e4'
                }}
                className={`
                    border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer
                    transition-colors bg-white hover:bg-stone-50
                    ${isDragging ? 'border-sage-500 bg-sage-50' : 'border-stone-200'}
                `}
                onClick={() => document.getElementById('file-upload')?.click()}
            >
                <input
                    id="file-upload"
                    type="file"
                    multiple
                    accept="image/*"
                    className="hidden"
                    onChange={handleFileSelect}
                />

                {isUploading ? (
                    <div className="flex flex-col items-center gap-3">
                        <Loader2 className="w-10 h-10 text-sage-500 animate-spin" />
                        <p className="text-stone-600 font-medium">Uploading...</p>
                    </div>
                ) : (
                    <div className="flex flex-col items-center gap-3">
                        <div className="w-14 h-14 rounded-full bg-sage-100 flex items-center justify-center">
                            <Upload className="w-7 h-7 text-sage-600" />
                        </div>
                        <div>
                            <p className="text-stone-800 font-semibold text-lg">
                                Drop photos here
                            </p>
                            <p className="text-stone-400 text-sm mt-1">
                                or click to browse
                            </p>
                        </div>
                    </div>
                )}
            </motion.div>

            <AnimatePresence>
                {uploadStatus && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className={`
                            mt-3 p-3 rounded-xl text-sm flex items-center justify-between
                            ${uploadStatus.success
                                ? 'bg-green-50 text-green-700 border border-green-200'
                                : 'bg-red-50 text-red-700 border border-red-200'
                            }
                        `}
                    >
                        <span>{uploadStatus.message}</span>
                        <button onClick={() => setUploadStatus(null)}>
                            <X size={16} />
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
