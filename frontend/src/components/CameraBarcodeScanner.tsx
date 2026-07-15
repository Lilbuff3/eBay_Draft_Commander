import { useEffect, useRef, useState, useCallback } from 'react'
import { Camera, CameraOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { normalizeIsbn, isLikelyIsbn, ScanDeduper, playScanBeep } from '@/lib/isbn'
import { useHaptics } from '@/hooks/useHaptics'

// Two-tier scanning:
//   native  — the browser's BarcodeDetector (Chrome Android). Fast + zero JS
//             decode cost, but format support varies by device/GMS version.
//   zxing   — pure-JS fallback (@zxing/browser) loaded lazily when the native
//             detector is missing OR can't cover every requested format. Reads
//             UPC-A/E + EAN-8/13 on any secure-context browser.
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

type ScanMode = 'native' | 'zxing'

interface CameraBarcodeScannerProps {
    onDetect: (code: string) => void
    /** BarcodeDetector/ZXing formats to request. Default: EAN-13 only (ISBN). */
    formats?: string[]
    /** Accept/reject a normalized code before onDetect fires. Default: ISBN check. */
    validate?: (code: string) => boolean
}

/**
 * Camera barcode scanner. Collapsed behind a toggle so desktop UX is unchanged;
 * the USB scanner and typed entry keep working regardless of camera support.
 */
export function CameraBarcodeScanner({ onDetect, formats = ['ean_13'], validate = isLikelyIsbn }: CameraBarcodeScannerProps) {
    const [active, setActive] = useState(false)
    const [mode, setMode] = useState<ScanMode>('native')
    const [unsupported, setUnsupported] = useState<string | null>(null)
    const videoRef = useRef<HTMLVideoElement | null>(null)
    const streamRef = useRef<MediaStream | null>(null)          // native path only
    const zxingControlsRef = useRef<{ stop: () => void } | null>(null)  // zxing path only
    const usableFormatsRef = useRef<string[]>(formats)          // native formats this browser supports
    const deduperRef = useRef(new ScanDeduper(3000))

    // Latest-value refs so the detect effects can run on [active, mode] alone
    // (parents pass fresh array/callback identities every render).
    const { success: hapticSuccess } = useHaptics()
    const hapticsRef = useRef(hapticSuccess)
    const onDetectRef = useRef(onDetect)
    const validateRef = useRef(validate)
    const formatsRef = useRef(formats)
    useEffect(() => {
        hapticsRef.current = hapticSuccess
        onDetectRef.current = onDetect
        validateRef.current = validate
        formatsRef.current = formats
    })

    const accept = useCallback((raw: string) => {
        const normalized = normalizeIsbn(raw)
        if (!validateRef.current(normalized)) return
        if (!deduperRef.current.shouldAccept(normalized)) return
        hapticsRef.current()
        playScanBeep('success')
        onDetectRef.current(normalized)
    }, [])

    const stop = useCallback(() => {
        streamRef.current?.getTracks().forEach(t => t.stop())
        streamRef.current = null
        zxingControlsRef.current?.stop()
        zxingControlsRef.current = null
        setActive(false)
    }, [])

    const start = useCallback(async () => {
        setUnsupported(null)
        // Prefer native only when it covers ALL requested formats; otherwise
        // ZXing, so a detector that lacks (e.g.) upc_a doesn't silently drop it.
        let chosen: ScanMode = 'zxing'
        const Detector = getBarcodeDetector()
        if (Detector) {
            try {
                const supported = await Detector.getSupportedFormats()
                const usable = formats.filter(f => supported.includes(f))
                if (usable.length === formats.length) {
                    usableFormatsRef.current = usable
                    chosen = 'native'
                }
            } catch {
                chosen = 'zxing'
            }
        }

        // Native pre-acquires the rear camera here; ZXing acquires it itself.
        if (chosen === 'native') {
            try {
                streamRef.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
            } catch (err) {
                console.warn('Camera unavailable:', err)
                toast.error('Camera unavailable — check permission, or use the USB scanner.')
                setUnsupported('Camera permission denied or unavailable — use your USB scanner or type the code below.')
                return
            }
        }
        setMode(chosen)
        setActive(true)
    }, [formats])

    // NATIVE detect loop
    useEffect(() => {
        if (!active || mode !== 'native' || !streamRef.current) return
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
                for (const code of codes) accept(code.rawValue)
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
    }, [active, mode, stop, accept])

    // ZXING fallback (lazy-loaded)
    useEffect(() => {
        if (!active || mode !== 'zxing') return
        const video = videoRef.current
        if (!video) return
        let cancelled = false
        let localControls: { stop: () => void } | null = null

        void (async () => {
            try {
                const [{ BrowserMultiFormatReader }, { DecodeHintType, BarcodeFormat }] = await Promise.all([
                    import('@zxing/browser'),
                    import('@zxing/library'),
                ])
                const byName: Record<string, number> = {
                    ean_13: BarcodeFormat.EAN_13,
                    ean_8: BarcodeFormat.EAN_8,
                    upc_a: BarcodeFormat.UPC_A,
                    upc_e: BarcodeFormat.UPC_E,
                    code_128: BarcodeFormat.CODE_128,
                    code_39: BarcodeFormat.CODE_39,
                }
                const wanted = formatsRef.current.map(f => byName[f]).filter((v): v is number => v !== undefined)
                const hints = new Map<number, unknown>()
                if (wanted.length) hints.set(DecodeHintType.POSSIBLE_FORMATS, wanted)

                const reader = new BrowserMultiFormatReader(hints)
                const controls = await reader.decodeFromConstraints(
                    { video: { facingMode: 'environment' } },
                    video,
                    (result) => { if (result) accept(result.getText()) },
                )
                if (cancelled) controls.stop()
                else { localControls = controls; zxingControlsRef.current = controls }
            } catch (err) {
                console.warn('Camera scanning unavailable (ZXing fallback):', err)
                if (!cancelled) {
                    toast.error('Camera unavailable — check permission, or use the USB scanner.')
                    setUnsupported('Camera scanning unavailable — use your USB scanner or type the code below.')
                    setActive(false)
                }
            }
        })()

        const onVisibility = () => { if (document.hidden) stop() }
        document.addEventListener('visibilitychange', onVisibility)
        return () => {
            cancelled = true
            localControls?.stop()
            zxingControlsRef.current = null
            document.removeEventListener('visibilitychange', onVisibility)
        }
    }, [active, mode, stop, accept])

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
                <Button variant="outline" onClick={start} className="self-start">
                    <Camera size={16} className="mr-1.5" /> Scan with camera
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
