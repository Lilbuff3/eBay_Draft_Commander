import type { ItemDraft } from './api'

// Merges server-derived draft values into the current draft without
// clobbering fields the user has edited. Socket job_update events re-fetch
// job details while the user may be mid-edit on the form; only untouched
// fields may be refreshed from the server. Empty server values never blank
// out an existing value.
export function mergeDraft(
    server: Partial<ItemDraft>,
    current: ItemDraft,
    touched: Set<string>
): ItemDraft {
    const out: ItemDraft = { ...current }
    for (const key of Object.keys(server) as Array<keyof ItemDraft>) {
        if (touched.has(key)) continue
        const value = server[key]
        if (value === undefined || value === null || value === '') continue
        if (key === 'itemSpecifics' && value && Object.keys(value).length === 0) continue
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ;(out as any)[key] = value
    }
    return out
}
