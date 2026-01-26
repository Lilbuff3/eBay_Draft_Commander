import { useState, useCallback, useRef } from 'react'
import { Upload, FileVideo, Play, AlertCircle, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { toast } from 'sonner' // Assuming sonner is available based on package.json

interface MediaFile {
    id: string
    file: File
    previewUrl: string
    type: 'image' | 'video'
}

interface MediaManagerProps {
    initialMedia?: MediaFile[]
    onMediaChange?: (media: MediaFile[]) => void
}

const MAX_VIDEO_SIZE = 150 * 1024 * 1024 // 150MB
const ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/quicktime'] // .mp4, .mov
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export function MediaManager({ initialMedia = [], onMediaChange }: MediaManagerProps) {
    const [mediaItems, setMediaItems] = useState<MediaFile[]>(initialMedia)
    const [dragActive, setDragActive] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const handleFiles = useCallback((files: FileList | null) => {
        if (!files) return

        const newItems: MediaFile[] = []

        Array.from(files).forEach(file => {
            const isVideo = file.type.startsWith('video/')
            const isImage = file.type.startsWith('image/')

            // Validation
            if (isVideo) {
                if (!ALLOWED_VIDEO_TYPES.includes(file.type)) {
                    toast.error(`Unsupported video format: ${file.name}. Use MP4 or MOV.`)
                    return
                }
                if (file.size > MAX_VIDEO_SIZE) {
                    toast.error(`Video too large: ${file.name}. Max 150MB.`)
                    return
                }
            } else if (isImage) {
                if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
                    toast.error(`Unsupported image format: ${file.name}`)
                    return
                }
            } else {
                toast.error(`Unsupported file type: ${file.name}`)
                return
            }

            // Create preview
            const previewUrl = URL.createObjectURL(file)
            newItems.push({
                id: crypto.randomUUID(),
                file,
                previewUrl,
                type: isVideo ? 'video' : 'image'
            })
        })

        if (newItems.length > 0) {
            setMediaItems(prev => {
                const updated = [...prev, ...newItems]
                onMediaChange?.(updated)
                return updated
            })
            toast.success(`added ${newItems.length} file(s)`)
        }
    }, [onMediaChange])

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setDragActive(false)
        handleFiles(e.dataTransfer.files)
    }

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setDragActive(true)
    }

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setDragActive(false)
    }

    const removeMedia = (id: string) => {
        setMediaItems(prev => {
            const updated = prev.filter(item => item.id !== id)
            onMediaChange?.(updated)
            return updated
        })
    }

    return (
        <div className="space-y-4">
            {/* Drop Zone */}
            <div
                className={cn(
                    "relative group cursor-pointer flex flex-col items-center justify-center w-full h-32 rounded-xl border-2 border-dashed transition-all duration-200",
                    dragActive
                        ? "border-blue-500 bg-blue-50/50 scale-[0.99]"
                        : "border-stone-200 bg-stone-50 hover:bg-stone-100 hover:border-stone-300"
                )}
                onDragEnter={handleDragOver}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    multiple
                    accept=".jpg,.jpeg,.png,.webp,.mp4,.mov"
                    onChange={(e) => handleFiles(e.target.files)}
                />

                <div className="flex flex-col items-center gap-2 text-stone-500 group-hover:text-stone-600">
                    <div className="p-3 bg-white rounded-full shadow-sm ring-1 ring-stone-900/5 group-hover:scale-110 transition-transform">
                        <Upload size={20} className="text-blue-500" />
                    </div>
                    <div className="text-center">
                        <p className="text-sm font-medium">Click or drag media here</p>
                        <p className="text-xs text-stone-400">
                            Support: JPG, PNG (Images) • MP4, MOV (Video, Max 150MB)
                        </p>
                    </div>
                </div>
            </div>

            {/* Media Grid */}
            {mediaItems.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {mediaItems.map((item) => (
                        <div
                            key={item.id}
                            className="group relative aspect-square rounded-lg overflow-hidden bg-stone-100 border border-stone-200 ring-offset-2 focus-within:ring-2 ring-blue-500"
                        >
                            {item.type === 'video' ? (
                                <div className="w-full h-full flex items-center justify-center bg-stone-900">
                                    <video
                                        src={item.previewUrl}
                                        className="w-full h-full object-cover opacity-80"
                                    />
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                                            <Play size={20} className="text-white fill-current ml-1" />
                                        </div>
                                    </div>
                                    <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/50 text-white text-[10px] uppercase font-bold tracking-wider flex items-center gap-1">
                                        <FileVideo size={10} /> Video
                                    </div>
                                </div>
                            ) : (
                                <img
                                    src={item.previewUrl}
                                    alt="Preview"
                                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                                />
                            )}

                            {/* Overlay Controls */}
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-start justify-end p-2 opacity-0 group-hover:opacity-100">
                                <Button
                                    size="icon"
                                    variant="destructive"
                                    className="h-7 w-7 rounded-lg shadow-sm"
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        removeMedia(item.id)
                                    }}
                                >
                                    <Trash2 size={14} />
                                </Button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {mediaItems.length === 0 && (
                <div className="flex items-center gap-2 text-xs text-amber-600 bg-amber-50 p-3 rounded-lg border border-amber-100">
                    <AlertCircle size={14} />
                    <span>Listing has no 2026-compliant media. Add a video to boost visibility.</span>
                </div>
            )}
        </div>
    )
}
