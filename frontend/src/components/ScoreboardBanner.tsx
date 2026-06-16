import { useQuery } from '@tanstack/react-query'
import { TrendingUp, Package, ShoppingBag, Clock } from 'lucide-react'
import { fetchAnalyticsSummary } from '@/lib/api'
import { useCommanderStore } from '@/store/useCommanderStore'
import { getStatusBucket } from '@/lib/status'
import { cn } from '@/lib/utils'

const MINUTES_PER_LISTING = 12

function formatTimeSaved(minutes: number): string {
    if (minutes === 0) return '0m'
    if (minutes < 60) return `${minutes}m`
    const h = Math.floor(minutes / 60)
    const m = minutes % 60
    return m === 0 ? `${h}h` : `${h}h ${m}m`
}

function formatRevenue(n: number): string {
    if (n >= 1000) return `$${(n / 1000).toFixed(1)}k`
    return `$${n.toFixed(0)}`
}

interface StatCard {
    label: string
    value: string
    icon: React.ElementType
    color: string
    bg: string
    border: string
}

export function ScoreboardBanner() {
    const jobs = useCommanderStore(state => state.jobs)

    const { data, isLoading } = useQuery({
        queryKey: ['analytics-summary', '30'],
        queryFn: () => fetchAnalyticsSummary('30'),
        staleTime: 5 * 60 * 1000,
        retry: 1,
    })

    const liveCount = jobs.filter(j => getStatusBucket(j.status) === 'live').length
    const totalCompleted = jobs.filter(j => j.status === 'completed' || j.status === 'scheduled').length
    const timeSavedMin = (data?.items_sold ?? totalCompleted) * MINUTES_PER_LISTING

    const stats: StatCard[] = [
        {
            label: 'Revenue · 30d',
            value: data ? formatRevenue(data.total_revenue) : '—',
            icon: TrendingUp,
            color: 'text-sage-600',
            bg: 'bg-sage-50',
            border: 'border-sage-100',
        },
        {
            label: 'Live on eBay',
            value: String(data?.active_listings_count ?? liveCount),
            icon: Package,
            color: 'text-persimmon-600',
            bg: 'bg-persimmon-50',
            border: 'border-persimmon-100',
        },
        {
            label: 'Sold · 30d',
            value: String(data?.items_sold ?? '—'),
            icon: ShoppingBag,
            color: 'text-ink-700',
            bg: 'bg-stone-50',
            border: 'border-stone-100',
        },
        {
            label: 'Time saved',
            value: formatTimeSaved(timeSavedMin),
            icon: Clock,
            color: 'text-amber-700',
            bg: 'bg-amber-50',
            border: 'border-amber-100',
        },
    ]

    if (isLoading) {
        return (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-[72px] bg-stone-100 rounded-2xl animate-pulse" />
                ))}
            </div>
        )
    }

    return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {stats.map((s) => (
                <div
                    key={s.label}
                    className={cn(
                        'flex flex-col gap-2 p-4 rounded-2xl border',
                        s.bg, s.border
                    )}
                >
                    <s.icon size={15} className={cn(s.color, 'opacity-70')} />
                    <div>
                        <p className={cn('font-display font-bold text-2xl leading-none tracking-tight', s.color)}>
                            {s.value}
                        </p>
                        <p className="text-[11px] text-stone-500 mt-1 font-medium">{s.label}</p>
                    </div>
                </div>
            ))}
        </div>
    )
}
