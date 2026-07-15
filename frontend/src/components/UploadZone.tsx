import { useState, useCallback } from 'react'
import { Upload, X, Loader2, Plus } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useCommanderStore } from '@/store/useCommanderStore'

interface UploadZoneProps {
    onUploadComplete?: (jobId: string) => void
    compact?: boolean
}

// Note: We intentionally do NOT set capture="environment" on mobile
// because it prevents users from selecting photos from their gallery.

export function UploadZone({ onUploadComplete, compact = false }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false)
    const [isUploading, setIsUploading] = useState(false)
    const [uploadStatus, setUploadStatus] = useState<{ success: boolean; message: string } | null>(null)
    const setUploadProgress = useCommanderStore(state => state.setUploadProgress)

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
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files
        if (!files || files.length === 0) return
        await uploadFiles(Array.from(files))
    }

    const uploadFiles = async (files: File[]) => {
        setIsUploading(true)
        setUploadStatus(null)
        setUploadProgress({ loaded: 0, total: 1, fileCount: files.length })

        const formData = new FormData()
        files.forEach(file => formData.append('files[]', file))

        try {
            const result = await new Promise<{ success: boolean; message?: string; error?: string; jobId?: string }>((resolve, reject) => {
                const xhr = new XMLHttpRequest()
                xhr.open('POST', '/api/upload')

                xhr.upload.onprogress = (e) => {
                    if (e.lengthComputable) {
                        setUploadProgress({ loaded: e.loaded, total: e.total, fileCount: files.length })
                    }
                }

                xhr.onload = () => {
                    try {
                        resolve(JSON.parse(xhr.responseText))
                    } catch {
                        reject(new Error('Invalid response'))
                    }
                }
                xhr.onerror = () => reject(new Error('Network error'))
                xhr.send(formData)
            })

            if (result.success) {
                setUploadStatus({ success: true, message: result.message || 'Upload complete' })
                onUploadComplete?.(result.jobId || '')
            } else {
                setUploadStatus({ success: false, message: result.error || 'Upload failed' })
            }
        } catch {
            setUploadStatus({ success: false, message: 'Network error' })
        } finally {
            setIsUploading(false)
            setUploadProgress(null)
        }
    }

    // Compact mode — slim single-line bar
    if (compact) {
        return (
            <div className="relative">
                <motion.div
                    onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleDrop}
                    animate={{
                        borderColor: isDragging ? '#F2622E' : '#e7e5e4'
                    }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            document.getElementById('file-upload')?.click()
                        }
                    }}
                    className={`
                        border-2 border-dashed rounded-xl px-4 py-3 cursor-pointer
                        transition-colors bg-white hover:bg-stone-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500 focus-visible:ring-offset-2
                        flex items-center justify-center gap-3
                        ${isDragging ? 'border-persimmon-400 bg-persimmon-50' : 'border-stone-200'}
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
                        aria-label="Upload files"
                    />

                    {isUploading ? (
                        <>
                            <Loader2 size={18} className="text-persimmon-600 animate-spin" />
                            <span className="text-sm text-stone-600 font-medium">Uploading…</span>
                        </>
                    ) : (
                        <>
                            <div className="w-8 h-8 rounded-full bg-persimmon-100 flex items-center justify-center flex-shrink-0">
                                <Plus size={16} className="text-persimmon-600" />
                            </div>
                            <span className="text-sm text-stone-600">
                                <span className="font-medium text-stone-700">Drop photos</span>
                                {' '}or click to add more items
                            </span>
                        </>
                    )}
                </motion.div>

                <AnimatePresence>
                    {uploadStatus && (
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0 }}
                            className={`
                                mt-2 px-3 py-2 rounded-lg text-sm flex items-center justify-between
                                ${uploadStatus.success
                                    ? 'bg-green-50 text-green-700 border border-green-200'
                                    : 'bg-red-50 text-red-700 border border-red-200'
                                }
                            `}
                        >
                            <span>{uploadStatus.message}</span>
                            <button
                                onClick={(e) => { e.stopPropagation(); setUploadStatus(null) }}
                                aria-label="Dismiss upload status"
                            >
                                <X size={14} />
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        )
    }

    // Full expanded mode
    return (
        <div className="relative">
            <motion.div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                animate={{
                    scale: isDragging ? 1.02 : 1,
                    borderColor: isDragging ? '#F2622E' : '#e7e5e4'
                }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        document.getElementById('file-upload-full')?.click()
                    }
                }}
                className={`
                    border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer
                    transition-colors bg-white hover:bg-stone-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500 focus-visible:ring-offset-2
                    ${isDragging ? 'border-persimmon-400 bg-persimmon-50' : 'border-stone-200'}
                `}
                onClick={() => document.getElementById('file-upload-full')?.click()}
            >
                <input
                    id="file-upload-full"
                    type="file"
                    multiple
                    accept="image/*"
                    className="hidden"
                    onChange={handleFileSelect}
                    aria-label="Upload files"
                />

                {isUploading ? (
                    <div className="flex flex-col items-center gap-3">
                        <Loader2 className="w-10 h-10 text-persimmon-600 animate-spin" />
                        <p className="text-stone-600 font-medium">Uploading…</p>
                    </div>
                ) : (
                    <div className="flex flex-col items-center gap-3">
                        <div className="w-14 h-14 rounded-full bg-persimmon-100 flex items-center justify-center">
                            <Upload className="w-7 h-7 text-persimmon-600" />
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
                        <button
                            onClick={() => setUploadStatus(null)}
                            aria-label="Dismiss upload status"
                        >
                            <X size={16} />
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
