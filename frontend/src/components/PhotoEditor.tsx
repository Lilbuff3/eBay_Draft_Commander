import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
    RotateCcw, RotateCw, FlipHorizontal, FlipVertical,
    Crop, Sparkles, Contrast, Sun, ZoomIn, ZoomOut,
    Undo2, Save, X, Wand2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface PhotoEditorProps {
    imagePath?: string
    jobId?: string
    onClose: () => void
    onSave?: () => void
}

interface Adjustment {
    brightness: number
    contrast: number
    saturation: number
    sharpness: number
}

const defaultAdjustments: Adjustment = {
    brightness: 50,
    contrast: 50,
    saturation: 50,
    sharpness: 50
}

export function PhotoEditor({ imagePath, jobId, onClose, onSave }: PhotoEditorProps) {
    const [rotation, setRotation] = useState(0)
    const [flipX, setFlipX] = useState(false)
    const [flipY, setFlipY] = useState(false)
    const [zoom, setZoom] = useState(100)
    const [adjustments, setAdjustments] = useState<Adjustment>(defaultAdjustments)
    const [_isCropping, _setIsCropping] = useState(false)
    const [isEnhancing, setIsEnhancing] = useState(false)
    const [hasChanges, setHasChanges] = useState(false)
    const [images, setImages] = useState<{ name: string; url: string }[]>([])
    const [selectedImage, setSelectedImage] = useState<string | null>(null)
    const [isLoadingImages, setIsLoadingImages] = useState(false)
    const [removeBackground, setRemoveBackground] = useState(false)
    const [isRemovingBg, setIsRemovingBg] = useState(false)

    // Fetch images from job folder
    useEffect(() => {
        if (!jobId) return

        setIsLoadingImages(true)
        fetch(`/api/job/${jobId}/images`)
            .then(res => res.json())
            .then(data => {
                setImages(data.images || [])
                if (data.images?.length > 0) {
                    setSelectedImage(data.images[0].url)
                }
            })
            .catch(err => console.error('Failed to load images:', err))
            .finally(() => setIsLoadingImages(false))
    }, [jobId])

    // Use selectedImage or passed imagePath
    const displayImage = selectedImage || imagePath

    const handleRotate = (direction: 'cw' | 'ccw') => {
        setRotation(prev => {
            const newRotation = direction === 'cw' ? prev + 90 : prev - 90
            return newRotation % 360
        })
        setHasChanges(true)
    }

    const handleFlip = (axis: 'x' | 'y') => {
        if (axis === 'x') setFlipX(prev => !prev)
        else setFlipY(prev => !prev)
        setHasChanges(true)
    }

    const handleAdjustment = (key: keyof Adjustment, value: number[]) => {
        setAdjustments(prev => ({ ...prev, [key]: value[0] }))
        setHasChanges(true)
    }

    const handleAutoEnhance = async () => {
        setIsEnhancing(true)
        // Simulate AI enhancement
        await new Promise(resolve => setTimeout(resolve, 1500))
        setAdjustments({
            brightness: 55,
            contrast: 58,
            saturation: 52,
            sharpness: 60
        })
        setIsEnhancing(false)
        setHasChanges(true)
    }

    const handleRemoveBackground = () => {
        setRemoveBackground(true)
        setHasChanges(true)
    }

    const handleReset = () => {
        setRotation(0)
        setFlipX(false)
        setFlipY(false)
        setZoom(100)
        setAdjustments(defaultAdjustments)
        setRemoveBackground(false)
        setHasChanges(false)
    }

    const handleSave = async () => {
        try {
            if (removeBackground) setIsRemovingBg(true)
            await fetch('/api/tools/photo/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jobId,
                    edits: {
                        rotation,
                        flipX,
                        flipY,
                        adjustments,
                        remove_background: removeBackground
                    }
                })
            })
            setRemoveBackground(false)
            setIsRemovingBg(false)
            onSave?.()
        } catch (error) {
            console.error('Failed to save photo:', error)
            setIsRemovingBg(false)
        }
    }

    // Generate CSS filter from adjustments
    const imageFilter = `
brightness(${adjustments.brightness / 50})
contrast(${adjustments.contrast / 50})
saturate(${adjustments.saturation / 50})
    `.trim()

    const imageTransform = `
rotate(${rotation}deg)
scaleX(${flipX ? - 1 : 1})
scaleY(${flipY ? - 1 : 1})
scale(${zoom / 100})
    `.trim()

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="bg-white rounded-3xl border border-stone-200 shadow-xl overflow-hidden"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-stone-100 bg-gradient-to-r from-blue-50 to-white">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-500 flex items-center justify-center text-white shadow-sm">
                        <Wand2 size={20} />
                    </div>
                    <div>
                        <h2 className="font-semibold text-stone-800">Photo Editor</h2>
                        <p className="text-xs text-stone-400">Transform and enhance images</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {hasChanges && (
                        <Badge variant="secondary" className="bg-amber-100 text-amber-700">
                            Unsaved Changes
                        </Badge>
                    )}
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <X size={18} />
                    </Button>
                </div>
            </div>

            <div className="flex">
                {/* Image Preview */}
                <div className="flex-1 p-6 min-h-[400px] bg-stone-50 flex flex-col">
                    <div className="flex-1 rounded-2xl bg-stone-100 overflow-hidden flex items-center justify-center relative">
                        {displayImage ? (
                            <img
                                src={displayImage}
                                alt="Edit preview"
                                style={{ filter: imageFilter, transform: imageTransform }}
                                className="max-w-full max-h-full object-contain transition-all duration-300"
                            />
                        ) : isLoadingImages ? (
                            <div className="text-stone-400 flex flex-col items-center">
                                <Crop size={48} className="animate-pulse" />
                                <span className="text-sm mt-2">Loading images...</span>
                            </div>
                        ) : (
                            <div className="text-stone-300 flex flex-col items-center">
                                <Crop size={48} />
                                <span className="text-sm mt-2">Select an image to edit</span>
                            </div>
                        )}

                        {/* Zoom Controls */}
                        <div className="absolute bottom-4 right-4 flex gap-1 bg-white/90 backdrop-blur-sm rounded-lg p-1 shadow-sm">
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => setZoom(prev => Math.max(25, prev - 25))}
                            >
                                <ZoomOut size={16} />
                            </Button>
                            <span className="text-xs font-medium text-stone-600 px-2 flex items-center">
                                {zoom}%
                            </span>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => setZoom(prev => Math.min(200, prev + 25))}
                            >
                                <ZoomIn size={16} />
                            </Button>
                        </div>
                    </div>

                    {/* Quick Actions */}
                    <div className="flex gap-2 mt-4 justify-center">
                        <Button variant="outline" size="sm" onClick={() => handleRotate('ccw')}>
                            <RotateCcw size={16} className="mr-1" /> Left
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handleRotate('cw')}>
                            <RotateCw size={16} className="mr-1" /> Right
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handleFlip('x')}>
                            <FlipHorizontal size={16} className="mr-1" /> H-Flip
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handleFlip('y')}>
                            <FlipVertical size={16} className="mr-1" /> V-Flip
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleRemoveBackground}
                            disabled={isRemovingBg}
                            className={cn(
                                "border-blue-200 hover:bg-blue-50 transition-all",
                                removeBackground && "bg-blue-50 border-blue-400 text-blue-600 shadow-inner"
                            )}
                            title="Auto-Background Removal"
                        >
                            <Wand2 size={16} className={cn("mr-1", isRemovingBg && "animate-spin")} />
                            {isRemovingBg ? 'Processing...' : removeBackground ? 'BG Marked' : 'Remove BG'}
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleAutoEnhance}
                            disabled={isEnhancing}
                            className="bg-gradient-to-r from-purple-50 to-pink-50 border-purple-200 hover:from-purple-100 hover:to-pink-100"
                        >
                            <Sparkles size={16} className={cn("mr-1", isEnhancing && "animate-spin")} />
                            {isEnhancing ? 'Enhancing...' : 'Auto Enhance'}
                        </Button>
                    </div>

                    {/* Image Thumbnails */}
                    {images.length > 1 && (
                        <div className="flex gap-2 mt-4 justify-center overflow-x-auto pb-2">
                            {images.map((img) => (
                                <button
                                    key={img.name}
                                    onClick={() => setSelectedImage(img.url)}
                                    className={`flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2 transition-all ${selectedImage === img.url
                                        ? 'border-blue-500 ring-2 ring-blue-200'
                                        : 'border-stone-200 hover:border-stone-300'
                                        }`}
                                >
                                    <img
                                        src={img.url}
                                        alt={img.name}
                                        className="w-full h-full object-cover"
                                    />
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Adjustments Panel */}
                <div className="w-72 border-l border-stone-100 p-6 space-y-6">
                    <Tabs defaultValue="adjust" className="w-full">
                        <TabsList className="w-full grid grid-cols-2">
                            <TabsTrigger value="adjust">Adjust</TabsTrigger>
                            <TabsTrigger value="filters">Filters</TabsTrigger>
                        </TabsList>

                        <TabsContent value="adjust" className="space-y-6 mt-4">
                            {/* Brightness */}
                            <div>
                                <div className="flex justify-between mb-2">
                                    <label className="text-sm font-medium text-stone-700 flex items-center gap-2">
                                        <Sun size={14} /> Brightness
                                    </label>
                                    <span className="text-xs text-stone-400">{adjustments.brightness}%</span>
                                </div>
                                <Slider
                                    value={[adjustments.brightness]}
                                    max={100}
                                    step={1}
                                    onValueChange={(v) => handleAdjustment('brightness', v)}
                                />
                            </div>

                            {/* Contrast */}
                            <div>
                                <div className="flex justify-between mb-2">
                                    <label className="text-sm font-medium text-stone-700 flex items-center gap-2">
                                        <Contrast size={14} /> Contrast
                                    </label>
                                    <span className="text-xs text-stone-400">{adjustments.contrast}%</span>
                                </div>
                                <Slider
                                    value={[adjustments.contrast]}
                                    max={100}
                                    step={1}
                                    onValueChange={(v) => handleAdjustment('contrast', v)}
                                />
                            </div>

                            {/* Saturation */}
                            <div>
                                <div className="flex justify-between mb-2">
                                    <label className="text-sm font-medium text-stone-700 flex items-center gap-2">
                                        <Sparkles size={14} /> Saturation
                                    </label>
                                    <span className="text-xs text-stone-400">{adjustments.saturation}%</span>
                                </div>
                                <Slider
                                    value={[adjustments.saturation]}
                                    max={100}
                                    step={1}
                                    onValueChange={(v) => handleAdjustment('saturation', v)}
                                />
                            </div>

                            {/* Sharpness */}
                            <div>
                                <div className="flex justify-between mb-2">
                                    <label className="text-sm font-medium text-stone-700 flex items-center gap-2">
                                        <Crop size={14} /> Sharpness
                                    </label>
                                    <span className="text-xs text-stone-400">{adjustments.sharpness}%</span>
                                </div>
                                <Slider
                                    value={[adjustments.sharpness]}
                                    max={100}
                                    step={1}
                                    onValueChange={(v) => handleAdjustment('sharpness', v)}
                                />
                            </div>
                        </TabsContent>

                        <TabsContent value="filters" className="mt-4">
                            <div className="grid grid-cols-3 gap-2">
                                {['Original', 'Vivid', 'B&W', 'Warm', 'Cool', 'Vintage'].map((filter) => (
                                    <button
                                        key={filter}
                                        className="aspect-square rounded-lg bg-stone-100 flex items-center justify-center text-xs font-medium text-stone-600 hover:bg-stone-200 transition-colors"
                                    >
                                        {filter}
                                    </button>
                                ))}
                            </div>
                        </TabsContent>
                    </Tabs>

                    {/* Action Buttons */}
                    <div className="pt-4 border-t border-stone-100 space-y-2">
                        <Button
                            className="w-full bg-blue-500 hover:bg-blue-600"
                            onClick={handleSave}
                            disabled={!hasChanges}
                        >
                            <Save size={16} className="mr-2" /> Save Changes
                        </Button>
                        <Button
                            variant="outline"
                            className="w-full"
                            onClick={handleReset}
                            disabled={!hasChanges}
                        >
                            <Undo2 size={16} className="mr-2" /> Reset All
                        </Button>
                    </div>
                </div>
            </div>
        </motion.div>
    )
}
