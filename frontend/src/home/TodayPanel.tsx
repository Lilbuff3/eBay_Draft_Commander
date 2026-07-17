import { useQuery } from '@tanstack/react-query'
import { Bot, FlaskConical } from 'lucide-react'
import { apiFetch } from '@/lib/api'

/**
 * TodayPanel — the autopilot's daily report on the home screen.
 *
 * Shows what the robot did (or, in dry-run, WOULD do) in its last cycle plus
 * how many price-discovery listings are live. Ship/review banners already
 * exist on the home, so this panel stays focused on the autonomous stuff.
 *
 * Eager-bundle rules: apiFetch + lucide only — never import a lazy tab body.
 */
interface TodayData {
    reviews: number
    queued: number
    discovery_live: number
    autopilot: {
        last_run_at: number
        dry_run: boolean
        offers: number
        markdowns: number
        relists: number
    } | null
}

const ago = (epoch: number) => {
    const hours = Math.max(0, (Date.now() / 1000 - epoch) / 3600)
    if (hours < 1) return 'just now'
    if (hours < 24) return `${Math.round(hours)}h ago`
    return `${Math.round(hours / 24)}d ago`
}

export function TodayPanel() {
    const { data } = useQuery({
        queryKey: ['today'],
        queryFn: () => apiFetch<TodayData>('/api/today'),
        refetchInterval: 5 * 60 * 1000,
    })

    if (!data) return null
    const ap = data.autopilot
    const hasContent = ap !== null || data.discovery_live > 0
    if (!hasContent) return null

    const actions: string[] = []
    if (ap) {
        if (ap.offers) actions.push(`${ap.offers} offer${ap.offers !== 1 ? 's' : ''} to watchers`)
        if (ap.markdowns) actions.push(`${ap.markdowns} price drop${ap.markdowns !== 1 ? 's' : ''}`)
        if (ap.relists) actions.push(`${ap.relists} relist${ap.relists !== 1 ? 's' : ''}`)
    }

    return (
        <div className="rounded-2xl bg-stone-100 border border-stone-200 px-4 py-3 space-y-1.5">
            {ap && (
                <div className="flex items-start gap-2.5">
                    <Bot className="w-4 h-4 text-persimmon-600 shrink-0 mt-0.5" />
                    <div className="text-sm text-ink-800 min-w-0">
                        <span className="font-bold">
                            Autopilot{ap.dry_run ? ' (dry run)' : ''} · {ago(ap.last_run_at)}:
                        </span>{' '}
                        {actions.length
                            ? `${ap.dry_run ? 'would do ' : ''}${actions.join(', ')}`
                            : 'nothing needed'}
                        {ap.dry_run && actions.length > 0 && (
                            <span className="text-stone-500"> — flip live in Settings → Autopilot</span>
                        )}
                    </div>
                </div>
            )}
            {data.discovery_live > 0 && (
                <div className="flex items-start gap-2.5">
                    <FlaskConical className="w-4 h-4 text-clay-600 shrink-0 mt-0.5" />
                    <div className="text-sm text-ink-800">
                        <span className="font-bold">{data.discovery_live}</span> price-discovery
                        listing{data.discovery_live !== 1 ? 's' : ''} live — listed high, auto-markdown finds the price
                    </div>
                </div>
            )}
        </div>
    )
}
