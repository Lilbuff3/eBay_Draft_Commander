// ISBN helpers shared by the camera scanner and the USB keyboard-wedge path.

/** Strip hyphens/spaces; uppercase a trailing ISBN-10 'x' check digit. */
export function normalizeIsbn(raw: string): string {
    return raw.replace(/[\s-]/g, '').toUpperCase()
}

/** True for a plausible ISBN-10 (9 digits + digit/X) or ISBN-13 (978/979). */
export function isLikelyIsbn(value: string): boolean {
    const s = normalizeIsbn(value)
    if (/^\d{9}[\dX]$/.test(s)) return true
    if (/^(978|979)\d{10}$/.test(s)) return true
    return false
}

/**
 * Rejects repeat reads of the same code within a time window. The camera
 * detector fires several times per second on a held barcode, and USB wedge
 * scanners occasionally double-trigger.
 */
export class ScanDeduper {
    private last = new Map<string, number>()
    constructor(private windowMs = 3000) { }

    shouldAccept(isbn: string, now: number = Date.now()): boolean {
        const prev = this.last.get(isbn)
        this.last.set(isbn, now)
        return prev === undefined || now - prev > this.windowMs
    }
}

/** Short WebAudio beep — no audio assets needed. */
export function playScanBeep(kind: 'success' | 'error') {
    try {
        type AudioCtor = typeof AudioContext
        const Ctx: AudioCtor | undefined = window.AudioContext
            ?? (window as unknown as { webkitAudioContext?: AudioCtor }).webkitAudioContext
        if (!Ctx) return
        const ctx = new Ctx()
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.type = 'sine'
        osc.frequency.value = kind === 'success' ? 1200 : 300
        gain.gain.setValueAtTime(0.15, ctx.currentTime)
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15)
        osc.connect(gain).connect(ctx.destination)
        osc.start()
        osc.stop(ctx.currentTime + 0.16)
        osc.onended = () => { void ctx.close() }
    } catch {
        // Audio unavailable — beep is a nicety, never an error
    }
}
