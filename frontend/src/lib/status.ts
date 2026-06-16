import { Loader2, Check, AlertCircle, type LucideIcon } from 'lucide-react'
import type { JobStatus } from '@/lib/api'

/**
 * Three-state model (capture-and-forget):
 *   Working   — app is analyzing / pricing / listing. You do nothing.
 *   Live      — on eBay (scheduled shows "Live at <time>" via the card subtitle).
 *   Needs you — a genuine error only the human/retry can resolve. Rare.
 *
 * Every underlying JobStatus collapses into one of these buckets.
 */
export type StatusBucket = 'working' | 'live' | 'needs_you'

export interface StatusStyle {
    bucket: StatusBucket
    label: string
    icon: LucideIcon
    /** text color class for the pill */
    text: string
    /** background tint class for the pill */
    bg: string
    /** accent border tint (used on photo cards) */
    border: string
    spin?: boolean
}

const WORKING: StatusStyle = {
    bucket: 'working', label: 'Working', icon: Loader2,
    text: 'text-persimmon-700', bg: 'bg-persimmon-100', border: 'border-persimmon-200', spin: true,
}
const LIVE: StatusStyle = {
    bucket: 'live', label: 'Live', icon: Check,
    text: 'text-sage-700', bg: 'bg-sage-100', border: 'border-sage-200',
}
const NEEDS_YOU: StatusStyle = {
    bucket: 'needs_you', label: 'Needs you', icon: AlertCircle,
    text: 'text-red-700', bg: 'bg-red-100', border: 'border-red-200',
}

const BUCKET: Record<JobStatus, StatusStyle> = {
    pending: WORKING,
    processing: WORKING,
    awaiting_condition: WORKING,
    paused: WORKING,
    skipped: WORKING,
    completed: LIVE,
    scheduled: LIVE,
    failed: NEEDS_YOU,
    // Legacy states (no longer emitted by the no-blocks pipeline) — surface as attention.
    needs_review: NEEDS_YOU,
    pending_review: NEEDS_YOU,
}

export function getStatusStyle(status: JobStatus): StatusStyle {
    return BUCKET[status] || WORKING
}

/** Which display bucket a job falls into — used for filtering. */
export function getStatusBucket(status: JobStatus): StatusBucket {
    return getStatusStyle(status).bucket
}

export const STATUS_BUCKET_LABEL: Record<StatusBucket, string> = {
    working: 'Working',
    live: 'Live',
    needs_you: 'Needs you',
}
