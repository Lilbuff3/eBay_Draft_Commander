import { useEffect, useRef, useState, useCallback } from 'react'
import { Camera, CameraOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { normalizeIsbn, isLikelyIsbn, ScanDeduper, playScanBeep } from '@/lib/isbn'
import { useHaptics } from '@/hooks/useHaptics'

// Native BarcodeDetector (Chrome Android; behind flags elsewhere). Defaults
// to ean_13 (ISBNs are Bookland EAN-13); callers like the Source tab pass
// wider formats (upc_a etc.) plus their own validate() to accept them.
interface DetectedBarcode { rawValue: string }
interface BarcodeDetectorLike {
    detect(source: CanvasImageSource): Promise<DetectedBarcode[]>
}
interface BarcodeDetectorCtor {
    new(options?: { formats: string[] }): BarcodeDetectorLike
    getSupportedFormats(): Promise<string[]>
}

function getBarcodeDetector(): BarcodeDetectorCtor | null {
    const ctor = (window as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector
    return ctor ?? null
}

interface CameraBarcodeScannerProps {
    onDetect: (code: string) => void
    /** BarcodeDetector formats to request. Default: EAN-13 only (ISBN). */
    formats?: string[]
    /** Accept/reject a normalized code before onDetect fires. Default: ISBN check. */
    validate?: (code: string) => boolean
}

/**
 * Camera-based ISBN scanner. Collapsed behind a toggle so desktop UX is
 * unchanged; when unsupported it shows an inline fallback message (the USB
 * scanner and typed entry keep working regardless).
 */
export function CameraBarcodeScanner({ onDetect, formats = ['ean_13'], validate = isLikelyIsbn }: CameraBarcodeScannerProps) {
    const [active, setActive] = useState(false)
    const [unsupported, setUnsupported] = useState<string | null>(null)
    const videoRef = useRef<HTMLVideoElement | null>(null)
    const streamRef = useRef<MediaStream | null>(null)
    const deduperRef = useRef(new ScanDeduper(3000))
    // Requested formats narrowed to what this browser actually supports (set in start())
    const usableFormatsRef = useRef<string[]>(formats)
    const { success: hapticSuccess } = useHaptics()

    const stop = useCallback(() => {
        streamRef.current?.getTracks().forEach(t => t.stop())
        streamRef.current = null
        setActive(false)
    }, [])

    const start = useCallback(async () => {
        const Detector = getBarcodeDetector()
        if (!Detector) {
            setUnsupported("Camera scanning isn't supported in this browser — use your USB scanner or type the ISBN below.")
            return
        }
        try {
            const supported = await Detector.getSupportedFormats()
            const usable = formats.filter(f => supported.includes(f))
            if (usable.length === 0) {
                setUnsupported('This browser cannot read these barcode formats — use your USB scanner or type the code below.')
                return
            }
            usableFormatsRef.current = usable
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            })
            streamRef.current = stream
            setActive(true)
        } catch (err) {
            console.warn('Camera unavailable:', err)
            toast.error('Camera unavailable — check permission, or use the USB scanner.')
            setUnsupported('Camera permission denied or unavailable — use your USB scanner or type the ISBN below.')
        }
    }, [formats])

    // Attach stream + run the detect loop while active
    useEffect(() => {
        if (!active || !streamRef.current) return
        const video = videoRef.current
        const Detector = getBarcodeDetector()
        if (!video || !Detector) return

        video.srcObject = streamRef.current
        void video.play().catch(() => { /* autoplay quirks; user can tap play */ })
        const detector = new Detector({ formats: usableFormatsRef.current })

        const interval = window.setInterval(async () => {
            if (video.readyState < 2) return
            try {
                const codes = await detector.detect(video)
                for (const code of codes) {
                    const normalized = normalizeIsbn(code.rawValue)
                    if (!validate(normalized)) continue
                    if (!deduperRef.current.shouldAccept(normalized)) continue
                    hapticSuccess()
                    playScanBeep('success')
                    onDetect(normalized)
                }
            } catch {
                // Transient detect failures (tab switch etc.) — keep looping
            }
        }, 200)

        const onVisibility = () => { if (document.hidden) stop() }
        document.addEventListener('visibilitychange', onVisibility)
        return () => {
            window.clearInterval(interval)
            document.removeEventListener('visibilitychange', onVisibility)
        }
    }, [active, onDetect, stop, hapticSuccess, validate])

    // Release the camera on unmount
    useEffect(() => stop, [stop])

    if (unsupported) {
        return (
            <div className="flex items-center gap-2 text-sm text-stone-500 bg-stone-100 rounded-lg px-3 py-2">
                <CameraOff size={16} className="shrink-0" />
                {unsupported}
            </div>
        )
    }

    return (
        <div className="flex flex-col gap-2">
            {!active ? (
                <Button variant="outline" size="sm" onClick={start} className="self-start">
                    <Camera size={15} className="mr-1.5" /> Scan with camera
                </Button>
            ) : (
                <div className="relative rounded-xl overflow-hidden bg-black max-w-md">
                    <video ref={videoRef} playsInline muted className="w-full max-h-64 object-cover" />
                    {/* Aim guide */}
                    <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                        <div className="w-3/4 h-16 border-2 border-white/70 rounded-lg" />
                    </div>
                    <Button
                        variant="secondary" size="sm" onClick={stop}
                        className="absolute top-2 right-2"
                    >
                        <CameraOff size={15} className="mr-1.5" /> Stop
                    </Button>
                </div>
            )}
        </div>
    )
}
