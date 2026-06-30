/**
 * Dead-stock signal for the Inventory cockpit.
 *
 * Uses ONLY age + watchers — eBay deprecated reliable per-listing views (HitCount),
 * so there is deliberately no "views" number here.
 *
 *   🔴 Dead  — older than DEAD_AGE days AND zero watchers (frozen capital)
 *   🟠 Stale — older than STALE_AGE days AND <= 1 watcher
 *   🟢 Warm  — >= WARM_WATCHERS watchers (likely to sell, leave alone)
 *      OK    — everything else
 *
 * Thresholds mirror the backend env vars (DEAD_STOCK_AGE_DAYS / STALE_AGE_DAYS /
 * WARM_WATCHERS); kept on the client because the raw signals (watchCount, startTime)
 * already come down with each listing.
 */
export type StaleTag = 'dead' | 'stale' | 'warm' | 'ok'

export const DEAD_AGE = 60
export const STALE_AGE = 30
export const WARM_WATCHERS = 3

export function ageDays(startTime?: string | null): number | null {
    if (!startTime) return null
    const t = Date.parse(startTime)
    if (isNaN(t)) return null
    return Math.max(0, Math.floor((Date.now() - t) / 86_400_000))
}

export function staleTag(watchCount: number, age: number | null): StaleTag {
    const w = watchCount || 0
    if (w >= WARM_WATCHERS) return 'warm'
    if (age != null && age > DEAD_AGE && w === 0) return 'dead'
    if (age != null && age > STALE_AGE && w <= 1) return 'stale'
    return 'ok'
}

export const TAG_META: Record<StaleTag, { label: string; chip: string; rank: number }> = {
    dead: { label: 'Dead', chip: 'bg-red-100 text-red-700', rank: 0 },
    stale: { label: 'Stale', chip: 'bg-amber-100 text-amber-700', rank: 1 },
    ok: { label: 'OK', chip: 'bg-stone-100 text-stone-500', rank: 2 },
    warm: { label: 'Warm', chip: 'bg-sage-100 text-sage-700', rank: 3 },
}

/** "47d" / "3d" / "—" when age unknown. */
export function ageLabel(age: number | null): string {
    return age == null ? '—' : `${age}d`
}
