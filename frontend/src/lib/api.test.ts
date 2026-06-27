import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiFetch, fetchPendingListings, fetchStats } from './api'

// api.ts imports `toast` from sonner at module load — stub it for a clean import.
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))

describe('apiFetch', () => {
    beforeEach(() => { vi.restoreAllMocks() })

    it('returns parsed JSON on a 2xx response', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ hello: 'world' }),
        }))
        const out = await apiFetch<{ hello: string }>('/api/x')
        expect(out).toEqual({ hello: 'world' })
    })

    it('throws with method, url, status and body on a non-2xx response', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            text: async () => 'boom',
        }))
        await expect(apiFetch('/api/x', { method: 'POST' }))
            .rejects.toThrow('API POST /api/x failed (500): boom')
    })

    it('still throws cleanly when the error body cannot be read', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: false,
            status: 404,
            text: async () => { throw new Error('no body') },
        }))
        await expect(apiFetch('/api/x')).rejects.toThrow('API GET /api/x failed (404):')
    })
})

describe('typed wrappers', () => {
    beforeEach(() => { vi.restoreAllMocks() })

    it('fetchPendingListings unwraps the listings array', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ listings: [{ id: 'a' }, { id: 'b' }] }),
        }))
        const out = await fetchPendingListings()
        expect(out).toHaveLength(2)
        expect(out[0].id).toBe('a')
    })

    it('fetchStats returns just the stats slice of the status payload', async () => {
        const stats = { pending: 1, completed: 2, failed: 0, total: 3 }
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                status: 'idle', stats, current_job: null,
                progress: { current: 0, total: 0, percent: 0 },
            }),
        }))
        const out = await fetchStats()
        expect(out).toEqual(stats)
    })
})
