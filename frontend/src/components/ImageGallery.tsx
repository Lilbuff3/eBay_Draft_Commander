import { useState } from 'react'
import { ChevronLeft, ChevronRight, Image as ImageIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors
} from '@dnd-kit/core'
import type { DragEndEvent } from '@dnd-kit/core'
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    horizontalListSortingStrategy,
    useSortable
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

interface GalleryImage {
    name: string
    url: string
}

interface ImageGalleryProps {
    images: GalleryImage[]
    onReorder?: (images: GalleryImage[]) => void
    jobId: string
    className?: string
}

// A Sortable Item component for the thumbnail strip
function SortableThumbnail({ img, index, selectedIndex, onSelect }: { img: GalleryImage, index: number, selectedIndex: number, onSelect: () => void }) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging
    } = useSortable({ id: img.name })

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 2 : 1,
    }

    return (
        <button
            ref={setNodeRef}
            style={style}
            {...attributes}
            {...listeners}
            onPointerDown={() => {
                // Allows click to select without disrupting drag
                if (!isDragging) {
                    onSelect()
                }
            }}
            className={cn(
                "relative w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 border-2 transition-all touch-none",
                index === selectedIndex
                    ? "border-sage-500 ring-1 ring-sage-500/30"
                    : "border-transparent hover:border-stone-300 opacity-70 hover:opacity-100",
                isDragging && "opacity-50 scale-105 shadow-xl border-sage-500"
            )}
        >
            <img
                src={img.url}
                alt={img.name}
                className="w-full h-full object-cover pointer-events-none"
            />
            {index === 0 && (
                <div className="absolute top-0 right-0 bg-yellow-400 text-yellow-900 text-[10px] font-bold px-1 rounded-bl-md z-10 pointers-event-none">
                    ★
                </div>
            )}
        </button>
    )
}

export function ImageGallery({ images, onReorder, jobId, className }: ImageGalleryProps) {
    const [selectedIndex, setSelectedIndex] = useState(0)

    // Ensure selectedIndex is valid within the current array bounds
    const safeSelectedIndex = images.length === 0 ? 0 : Math.min(selectedIndex, images.length - 1)

    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 5, // requires 5px movement before dragging starts
            },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    )

    if (images.length === 0) {
        return (
            <div className={cn("bg-stone-100 rounded-2xl flex items-center justify-center", className)} style={{ minHeight: '200px' }}>
                <div className="text-stone-300 flex flex-col items-center gap-2">
                    <ImageIcon size={40} />
                    <span className="text-sm">No images</span>
                </div>
            </div>
        )
    }

    const currentImage = images[safeSelectedIndex]
    const imageUrl = currentImage?.url || (currentImage ? `/api/job/${jobId}/image/${currentImage.name}` : '')

    const goNext = () => setSelectedIndex((i) => Math.min(i + 1, images.length - 1))
    const goPrev = () => setSelectedIndex((i) => Math.max(i - 1, 0))

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event

        if (over && active.id !== over.id) {
            const oldIndex = images.findIndex((img) => img.name === active.id)
            const newIndex = images.findIndex((img) => img.name === over.id)

            const newImages = arrayMove(images, oldIndex, newIndex)
            
            // If the user was looking at the exact image they dragged, update selected index to track it
            if (safeSelectedIndex === oldIndex) {
                setSelectedIndex(newIndex)
            } else if (
                (oldIndex < safeSelectedIndex && newIndex >= safeSelectedIndex) ||
                (oldIndex > safeSelectedIndex && newIndex <= safeSelectedIndex)
            ) {
                // Adjust selected index if it was bumped by the drag
                setSelectedIndex((i) => i + (oldIndex < newIndex ? -1 : 1))
            }

            if (onReorder) {
                onReorder(newImages)
            }
        }
    }

    return (
        <div className={cn("space-y-2", className)}>
            {/* Large Preview */}
            <div className="relative aspect-[4/3] bg-stone-100 rounded-2xl overflow-hidden group">
                <img
                    src={imageUrl}
                    alt={currentImage?.name || 'Preview'}
                    className="w-full h-full object-contain"
                />

                {/* Primary Photo Badge */}
                {safeSelectedIndex === 0 && images.length > 0 && (
                    <div className="absolute top-3 left-3 bg-yellow-400/90 backdrop-blur-sm text-yellow-900 text-xs font-bold px-3 py-1.5 rounded-full shadow-sm flex items-center gap-1.5">
                        <span>★</span> Primary Photo
                    </div>
                )}

                {/* Navigation Arrows */}
                {images.length > 1 && (
                    <>
                        {safeSelectedIndex > 0 && (
                            <button
                                onClick={(e) => { e.stopPropagation(); goPrev() }}
                                className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white p-1.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                                aria-label="Previous image"
                            >
                                <ChevronLeft size={18} />
                            </button>
                        )}
                        {safeSelectedIndex < images.length - 1 && (
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
                            {safeSelectedIndex + 1} / {images.length}
                        </div>
                    </>
                )}
            </div>

            {/* Thumbnail Strip (Sortable) */}
            {images.length > 1 && (
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleDragEnd}
                >
                    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
                        <SortableContext
                            items={images.map(img => img.name)}
                            strategy={horizontalListSortingStrategy}
                        >
                            {images.map((img, index) => {
                                const thumbUrl = img.url || `/api/job/${jobId}/image/${img.name}`
                                return (
                                    <SortableThumbnail 
                                        key={img.name} 
                                        img={{ ...img, url: thumbUrl }} 
                                        index={index} 
                                        selectedIndex={safeSelectedIndex} 
                                        onSelect={() => setSelectedIndex(index)} 
                                    />
                                )
                            })}
                        </SortableContext>
                    </div>
                </DndContext>
            )}
        </div>
    )
}
