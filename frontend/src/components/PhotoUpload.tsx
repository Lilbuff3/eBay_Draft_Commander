import { useState, useRef } from 'react'
import { Upload, Camera, Image as ImageIcon, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

interface PhotoUploadProps {
    onPhotosSelected: (files: File[]) => void
    maxPhotos?: number
}

export function PhotoUpload({ onPhotosSelected, maxPhotos = 12 }: PhotoUploadProps) {
    const [photos, setPhotos] = useState<File[]>([])
    const [isDragging, setIsDragging] = useState(false)
    const [previews, setPreviews] = useState<string[]>([])
    const fileInputRef = useRef<HTMLInputElement>(null)
    const cameraInputRef = useRef<HTMLInputElement>(null)

    const handleFiles = (files: FileList | null) => {
        if (!files) return

        const fileArray = Array.from(files)
        const imageFiles = fileArray.filter(file => file.type.startsWith('image/'))

        if (imageFiles.length === 0) {
            toast.error('Please select image files')
            return
        }

        if (photos.length + imageFiles.length > maxPhotos) {
            toast.error(`Maximum ${maxPhotos} photos allowed`)
            return
        }

        // Create preview URLs
        const newPreviews = imageFiles.map(file => URL.createObjectURL(file))

        setPhotos(prev => [...prev, ...imageFiles])
        setPreviews(prev => [...prev, ...newPreviews])
        onPhotosSelected([...photos, ...imageFiles])

        toast.success(`${imageFiles.length} photo${imageFiles.length > 1 ? 's' : ''} added`)
    }

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(true)
    }

    const handleDragLeave = () => {
        setIsDragging(false)
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
        handleFiles(e.dataTransfer.files)
    }

    const removePhoto = (index: number) => {
        URL.revokeObjectURL(previews[index])
        setPhotos(prev => prev.filter((_, i) => i !== index))
        setPreviews(prev => prev.filter((_, i) => i !== index))
        onPhotosSelected(photos.filter((_, i) => i !== index))
    }

    const openGallery = () => {
        fileInputRef.current?.click()
    }

    const openCamera = () => {
        cameraInputRef.current?.click()
    }

    return (
        <div className="space-y-4">
            {/* Upload Area */}
            <Card
                className={cn(
                    "border-2 border-dashed transition-colors cursor-pointer",
                    isDragging
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
                        : "border-slate-300 dark:border-slate-700 hover:border-blue-400"
                )}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={openGallery}
            >
                <div className="p-8 text-center">
                    <Upload className="mx-auto mb-4 text-slate-400" size={48} />
                    <h3 className="text-lg font-semibold mb-2">
                        Upload Photos
                    </h3>
                    <p className="text-sm text-slate-500 mb-4">
                        Drag and drop, or tap to browse
                    </p>
                    <div className="flex gap-2 justify-center flex-wrap">
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                                e.stopPropagation()
                                openGallery()
                            }}
                            className="tap-target"
                        >
                            <ImageIcon size={16} className="mr-2" />
                            Gallery
                        </Button>
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                                e.stopPropagation()
                                openCamera()
                            }}
                            className="tap-target md:hidden" // Camera only on mobile
                        >
                            <Camera size={16} className="mr-2" />
                            Camera
                        </Button>
                    </div>
                    <p className="text-xs text-slate-400 mt-4">
                        {photos.length}/{maxPhotos} photos
                    </p>
                </div>
            </Card>

            {/* Hidden file inputs */}
            <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => handleFiles(e.target.files)}
                className="hidden"
            />
            <input
                ref={cameraInputRef}
                type="file"
                accept="image/*"
                capture="environment" // Use rear camera by default
                onChange={(e) => handleFiles(e.target.files)}
                className="hidden"
            />

            {/* Photo Previews */}
            {previews.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {previews.map((preview, index) => (
                        <div key={preview} className="relative group">
                            <img
                                src={preview}
                                alt={`Photo ${index + 1}`}
                                className="w-full h-32 object-cover rounded-lg border border-slate-200 dark:border-slate-700"
                            />
                            <button
                                type="button"
                                onClick={() => removePhoto(index)}
                                className="absolute top-2 right-2 p-1 bg-red-500 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity tap-target"
                                aria-label="Remove photo"
                            >
                                <X size={16} />
                            </button>
                            {index === 0 && (
                                <div className="absolute bottom-2 left-2 px-2 py-1 bg-blue-500 text-white text-xs rounded">
                                    Cover
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
