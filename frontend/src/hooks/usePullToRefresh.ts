import { useEffect, useState, useRef, useCallback } from 'react'
import { useHaptics } from './useHaptics'

interface UsePullToRefreshOptions {
    onRefresh: () => Promise<void> | void
    threshold?: number
    isEnabled?: boolean
}

export function usePullToRefresh({
    onRefresh,
    threshold = 80,
    isEnabled = true,
}: UsePullToRefreshOptions) {
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [pullDistance, setPullDistance] = useState(0)
    const { tap, success } = useHaptics()

    // Use refs to avoid re-registering listeners on every state change
    const pullDistanceRef = useRef(0)
    const onRefreshRef = useRef(onRefresh)
    onRefreshRef.current = onRefresh
    const hapticFiredRef = useRef(false)
    const tapRef = useRef(tap)
    const successRef = useRef(success)

    const updatePullDistance = useCallback((distance: number) => {
        pullDistanceRef.current = distance
        setPullDistance(distance)
    }, [])

    useEffect(() => {
        if (!isEnabled) return

        let startY = 0
        let isPulling = false

        const handleTouchStart = (e: TouchEvent) => {
            // Only trigger if at top of page
            if (window.scrollY === 0) {
                startY = e.touches[0].clientY
                isPulling = true
                hapticFiredRef.current = false
            }
        }

        const handleTouchMove = (e: TouchEvent) => {
            if (!isPulling) return

            const currentY = e.touches[0].clientY
            const distance = currentY - startY

            // Only allow pulling down
            if (distance > 0) {
                // Prevent default scrolling behavior
                e.preventDefault()

                // Apply resistance (diminishing returns as you pull further)
                const resistance = 2.5
                const clamped = Math.min(distance / resistance, threshold * 1.5)
                updatePullDistance(clamped)

                // Haptic tick when crossing the threshold
                if (clamped >= threshold && !hapticFiredRef.current) {
                    hapticFiredRef.current = true
                    tapRef.current()
                }
            }
        }

        const handleTouchEnd = async () => {
            if (!isPulling) return

            isPulling = false

            if (pullDistanceRef.current >= threshold) {
                setIsRefreshing(true)
                try {
                    await onRefreshRef.current()
                    successRef.current()
                } finally {
                    setIsRefreshing(false)
                    updatePullDistance(0)
                }
            } else {
                updatePullDistance(0)
            }
        }

        document.addEventListener('touchstart', handleTouchStart, { passive: true })
        document.addEventListener('touchmove', handleTouchMove, { passive: false })
        document.addEventListener('touchend', handleTouchEnd)

        return () => {
            document.removeEventListener('touchstart', handleTouchStart)
            document.removeEventListener('touchmove', handleTouchMove)
            document.removeEventListener('touchend', handleTouchEnd)
        }
    }, [threshold, isEnabled, updatePullDistance])

    return { isRefreshing, pullDistance }
}
