import { useEffect, useState } from 'react'

/**
 * Reactive hook that tracks whether the viewport is mobile (<768px).
 * Uses matchMedia for efficient, event-driven updates (handles rotation, resize).
 */
export function useIsMobile() {
    const [isMobile, setIsMobile] = useState(
        typeof window !== 'undefined' && window.innerWidth < 768
    )
    useEffect(() => {
        const mq = window.matchMedia('(max-width: 767px)')
        const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
        setIsMobile(mq.matches)
        mq.addEventListener('change', handler)
        return () => mq.removeEventListener('change', handler)
    }, [])
    return isMobile
}
