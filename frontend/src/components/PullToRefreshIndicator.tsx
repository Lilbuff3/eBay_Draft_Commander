import { Loader2 } from 'lucide-react'

interface PullToRefreshIndicatorProps {
    pullDistance: number
    isRefreshing: boolean
    threshold?: number
}

export function PullToRefreshIndicator({
    pullDistance,
    isRefreshing,
    threshold = 80,
}: PullToRefreshIndicatorProps) {
    const progress = Math.min((pullDistance / threshold) * 100, 100)
    const opacity = Math.min(pullDistance / threshold, 1)

    if (pullDistance === 0 && !isRefreshing) {
        return null
    }

    return (
        <div
            className="fixed top-0 left-0 right-0 z-40 flex justify-center pointer-events-none"
            style={{
                transform: `translateY(${Math.min(pullDistance, threshold)}px)`,
                opacity,
                transition: pullDistance === 0 ? 'all 0.3s ease-out' : 'none',
            }}
        >
            <div className="bg-white dark:bg-slate-900 rounded-full shadow-lg p-3 mt-2">
                {isRefreshing ? (
                    <Loader2 className="animate-spin text-blue-600" size={24} />
                ) : (
                    <svg
                        className="text-blue-600"
                        width="24"
                        height="24"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        style={{
                            transform: `rotate(${progress * 1.8}deg)`,
                            transition: 'transform 0.1s',
                        }}
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                        />
                    </svg>
                )}
            </div>
        </div>
    )
}
