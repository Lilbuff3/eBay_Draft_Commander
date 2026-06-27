import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock module deps BEFORE importing the store (the store imports both at load).
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))
vi.mock('@/lib/api', () => ({
    startQueue: vi.fn().mockResolvedValue({ success: true }),
    pauseQueue: vi.fn().mockResolvedValue({ success: true }),
    scanInbox: vi.fn(),
    fetchJobs: vi.fn().mockResolvedValue([]),
    fetchPendingListings: vi.fn(),
    quickEditListing: vi.fn().mockResolvedValue({ success: true }),
    approvePendingListings: vi.fn(),
    deleteJob: vi.fn().mockResolvedValue({ success: true }),
}))

import { useCommanderStore } from './useCommanderStore'
import * as api from '@/lib/api'

const get = () => useCommanderStore.getState()

beforeEach(() => {
    useCommanderStore.setState({
        jobs: [], pendingListings: [], selectedJob: null,
        jobLogs: {}, isScanning: false, scanMessage: null, activeFilter: 'all',
    })
    vi.clearAllMocks()
})

describe('store setters', () => {
    it('setJobs replaces the jobs array', () => {
        get().setJobs([{ id: '1' } as never])
        expect(get().jobs).toHaveLength(1)
    })

    it('setActiveTab updates tab, records previous, and persists to localStorage', () => {
        useCommanderStore.setState({ activeTab: 'dashboard' })
        get().setActiveTab('settings')
        expect(get().activeTab).toBe('settings')
        expect(get().previousTab).toBe('dashboard')
        expect(localStorage.getItem('activeTab')).toBe('settings')
    })

    it('addLog appends and caps history at 100 entries', () => {
        for (let i = 0; i < 130; i++) get().addLog('job1', { message: `m${i}` } as never)
        const logs = get().jobLogs['job1']
        expect(logs).toHaveLength(100)
        expect(logs[logs.length - 1].message).toBe('m129')
    })
})

describe('store actions', () => {
    it('handleStart calls startQueue', async () => {
        await get().handleStart()
        expect(api.startQueue).toHaveBeenCalledOnce()
    })

    it('handleScan populates jobs and auto-selects the first on success', async () => {
        ;(api.scanInbox as ReturnType<typeof vi.fn>).mockResolvedValue({ success: true, added: 2 })
        ;(api.fetchJobs as ReturnType<typeof vi.fn>).mockResolvedValue([{ id: 'a' }, { id: 'b' }])
        await get().handleScan()
        expect(get().jobs).toHaveLength(2)
        expect(get().selectedJob?.id).toBe('a')
        expect(get().isScanning).toBe(false)
    })

    it('updatePending optimistically merges updates into the matching listing', async () => {
        useCommanderStore.setState({ pendingListings: [{ id: 'x', price: '1' } as never] })
        await get().updatePending('x', { price: '9.99' })
        expect(get().pendingListings[0].price).toBe('9.99')
        expect(api.quickEditListing).toHaveBeenCalledWith('x', { price: '9.99' })
    })

    it('approvePending removes approved ids from pending', async () => {
        ;(api.approvePendingListings as ReturnType<typeof vi.fn>).mockResolvedValue({ success: true, approved_count: 1 })
        useCommanderStore.setState({ pendingListings: [{ id: 'x' } as never, { id: 'y' } as never] })
        await get().approvePending(['x'])
        expect(get().pendingListings.map(l => l.id)).toEqual(['y'])
    })

    it('deletePending removes the listing locally', async () => {
        useCommanderStore.setState({ pendingListings: [{ id: 'x' } as never, { id: 'y' } as never] })
        await get().deletePending('x')
        expect(get().pendingListings.map(l => l.id)).toEqual(['y'])
    })
})
