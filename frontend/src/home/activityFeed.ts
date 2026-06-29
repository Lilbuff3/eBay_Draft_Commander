import { type Job } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'

export interface ActivityEvent {
    id: string
    text: string
    tone: 'persimmon' | 'sage' | 'clay' | 'ink'
    time: string
}

function fmtTime(iso: string | null | undefined): string {
    if (!iso) return ''
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    return d.toTimeString().slice(0, 5)
}

/**
 * Derives a "Commander · Live" activity feed from the real jobs list.
 *
 * This is the honest version of the HTML mock's streaming AI log: the backend
 * exposes coarse job statuses (not granular "identifying → pricing" phases), so
 * we surface real state transitions instead. If you later emit per-job progress
 * events (Socket.IO / SSE), feed those in here for the play-by-play effect.
 */
export function buildActivityFeed(jobs: Job[], limit = 6): ActivityEvent[] {
    const withTime = jobs
        .map(j => ({ j, t: j.completed_at || j.started_at || '' }))
        .filter(x => x.t)
        .sort((a, b) => (a.t < b.t ? 1 : -1))
        .slice(0, limit)

    return withTime.map(({ j }) => {
        const bucket = getStatusBucket(j.status)
        const name = j.display_name || j.name
        if (bucket === 'live') {
            return { id: j.id, text: `${name} · published live`, tone: 'sage', time: fmtTime(j.completed_at) }
        }
        if (bucket === 'needs_you') {
            return { id: j.id, text: `${name} · needs attention`, tone: 'persimmon', time: fmtTime(j.started_at) }
        }
        return { id: j.id, text: `${name} · analyzing`, tone: 'clay', time: fmtTime(j.started_at) }
    })
}

export const TONE_DOT: Record<ActivityEvent['tone'], string> = {
    persimmon: 'bg-persimmon-500',
    sage: 'bg-sage-500',
    clay: 'bg-clay-500',
    ink: 'bg-ink-500',
}
export const TONE_HALO: Record<ActivityEvent['tone'], string> = {
    persimmon: 'ring-persimmon-100',
    sage: 'ring-sage-100',
    clay: 'ring-clay-300/40',
    ink: 'ring-stone-200',
}
