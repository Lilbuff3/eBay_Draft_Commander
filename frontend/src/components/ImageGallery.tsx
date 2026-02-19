import { useState } from 'react'
import { ChevronLeft, ChevronRight, Image } from 'lucide-react'
import { cn } from '@/lib/utils'

interface GalleryImage {
    name: string
    url: string
}

interface ImageGalleryProps {
    images: GalleryImage[]
    jobId: string
    className?: string
}

export function ImageGallery({ images, jobId, className }: ImageGalleryProps) {
    const [selectedIndex, setSelectedIndex] = useState(0)

    if (images.length === 0) {
        return (
            <div className={cn("bg-stone-100 rounded-2xl flex items-center justify-center", className)} style={{ minHeight: '200px' }}>
                <div className="text-stone-300 flex flex-col items-center gap-2">
                    <Image size={40} />
                    <span className="text-sm">No images</span>
                </div>
            </div>
        )
    }

    const currentImage = images[selectedIndex]
    const imageUrl = currentImage.url || `/api/job/${jobId}/image/${currentImage.name}`

    const goNext = () => setSelectedIndex((i) => Math.min(i + 1, images.length - 1))
    const goPrev = () => setSelectedIndex((i) => Math.max(i - 1, 0))

    return (
        <div className={cn("space-y-2", className)}>
            {/* Large Preview */}
            <div className="relative aspect-[4/3] bg-stone-100 rounded-2xl overflow-hidden group">
                <img
                    src={imageUrl}
                    alt={currentImage.name}
                    className="w-full h-full object-contain"
                />

                {/* Navigation Arrows */}
                {images.length > 1 && (
                    <>
                        {selectedIndex > 0 && (
                            <button
                                onClick={(e) => { e.stopPropagation(); goPrev() }}
                                className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white p-1.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                                aria-label="Previous image"
                            >
                                <ChevronLeft size={18} />
                            </button>
                        )}
                        {selectedIndex < images.length - 1 && (
                            <button
                                onClick={(e) => { e.stopPropagation(); goNext() }}
                                className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white p-1.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                                aria-label="Next image"
                            >
                                <ChevronRight size={18} />
                            </button>
                        )}

                        {/* Image Counter */}
                        <div className="absolute bottom-2 right-2 bg-black/50 text-white text-xs px-2 py-1 rounded-lg backdrop-blur-sm">
                            {selectedIndex + 1} / {images.length}
                        </div>
                    </>
                )}
            </div>

            {/* Thumbnail Strip */}
            {images.length > 1 && (
                <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
                    {images.map((img, index) => {
                        const thumbUrl = img.url || `/api/job/${jobId}/image/${img.name}`
                        return (
                            <button
                                key={img.name}
                                onClick={() => setSelectedIndex(index)}
                                className={cn(
                                    "w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 border-2 transition-all",
                                    index === selectedIndex
                                        ? "border-sage-500 ring-1 ring-sage-500/30"
                                        : "border-transparent hover:border-stone-300 opacity-70 hover:opacity-100"
                                )}
                            >
                                <img
                                    src={thumbUrl}
                                    alt={img.name}
                                    className="w-full h-full object-cover"
                                />
                            </button>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
