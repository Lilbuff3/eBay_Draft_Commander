import { useEffect, useState } from 'react'

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

    useEffect(() => {
        if (!isEnabled) return

        let startY = 0
        let currentY = 0
        let isPulling = false

        const handleTouchStart = (e: TouchEvent) => {
            // Only trigger if at top of page
            if (window.scrollY === 0) {
                startY = e.touches[0].clientY
                isPulling = true
            }
        }

        const handleTouchMove = (e: TouchEvent) => {
            if (!isPulling) return

            currentY = e.touches[0].clientY
            const distance = currentY - startY

            // Only allow pulling down
            if (distance > 0) {
                // Prevent default scrolling behavior
                e.preventDefault()

                // Apply resistance (diminishing returns as you pull further)
                const resistance = 2.5
                setPullDistance(Math.min(distance / resistance, threshold * 1.5))
            }
        }

        const handleTouchEnd = async () => {
            if (!isPulling) return

            isPulling = false

            if (pullDistance >= threshold) {
                setIsRefreshing(true)
                try {
                    await onRefresh()
                } finally {
                    setIsRefreshing(false)
                    setPullDistance(0)
                }
            } else {
                setPullDistance(0)
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
    }, [onRefresh, threshold, isEnabled, pullDistance])

    return { isRefreshing, pullDistance }
}
