import { useEffect, useRef, useState } from 'react'

/**
 * Animates a number from 0 → `target` with an ease-out curve.
 * Uses setInterval (NOT requestAnimationFrame) so it still advances when the
 * tab is backgrounded — rAF is throttled there and would leave the value at 0.
 */
export function useCountUp(target: number, durationMs = 1150): number {
    const [value, setValue] = useState(target === 0 ? 0 : 0)
    const startRef = useRef<number>(0)

    useEffect(() => {
        startRef.current = Date.now()
        const id = setInterval(() => {
            const t = Math.min(1, (Date.now() - startRef.current) / durationMs)
            const eased = 1 - Math.pow(1 - t, 3)
            setValue(Math.round(target * eased))
            if (t >= 1) clearInterval(id)
        }, 16)
        return () => clearInterval(id)
    }, [target, durationMs])

    return value
}
