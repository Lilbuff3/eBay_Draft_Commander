import { create } from 'zustand'
import { type Job, type QueueStats, startQueue, pauseQueue, scanInbox, fetchJobs, fetchPendingListings, quickEditListing, approvePendingListings, deleteJob } from '@/lib/api'
import { type LogEntry } from '@/components/LogViewer'
import { toast } from 'sonner'

interface CommanderState {
    // Navigation
    activeTab: string
    previousTab: string
    setActiveTab: (tab: string) => void

    // Job Data
    jobs: Job[]
    setJobs: (jobs: Job[]) => void
    selectedJob: Job | null
    setSelectedJob: (job: Job | null) => void
    pendingListings: Job[]
    setPendingListings: (listings: Job[]) => void

    // Queue Status
    queueStats: QueueStats
    setQueueStats: (stats: QueueStats) => void
    isProcessing: boolean
    setIsProcessing: (isProcessing: boolean) => void
    ebayStatus: 'connected' | 'disconnected' | 'checking'
    setEbayStatus: (status: 'connected' | 'disconnected' | 'checking') => void

    // Logs
    jobLogs: Record<string, LogEntry[]>
    setJobLogs: (logs: Record<string, LogEntry[]>) => void
    addLog: (jobId: string, log: LogEntry) => void

    // Scanning State
    isScanning: boolean
    setIsScanning: (isScanning: boolean) => void
    scanMessage: string | null
    setScanMessage: (message: string | null) => void

    // Actions
    handleStart: () => Promise<void>
    handlePause: () => Promise<void>
    handleScan: () => Promise<void>
    fetchPending: () => Promise<void>
    updatePending: (id: string, updates: { title?: string; price?: string; condition?: string }) => Promise<void>
    approvePending: (ids: string[]) => Promise<void>
    deletePending: (id: string, deleteFolder?: boolean) => Promise<void>

    // Filtering & UI
    activeFilter: string
    setActiveFilter: (filter: string) => void
    batchSummary: {
        succeeded: number;
        failed: number;
        total_value: number;
        avg_time: number;
        total_duration: number;
    } | null
    setBatchSummary: (summary: CommanderState['batchSummary']) => void
}

export const useCommanderStore = create<CommanderState>((set, get) => ({
    // Navigation
    activeTab: localStorage.getItem('activeTab') || 'dashboard',
    previousTab: 'dashboard',
    setActiveTab: (tab) => {
        const current = get().activeTab
        localStorage.setItem('activeTab', tab)
        set({ activeTab: tab, previousTab: current })
    },

    // Job Data
    jobs: [],
    setJobs: (jobs) => set({ jobs }),
    selectedJob: null,
    setSelectedJob: (job) => set({ selectedJob: job }),
    pendingListings: [],
    setPendingListings: (pendingListings) => set({ pendingListings }),

    // Queue Status
    queueStats: { pending: 0, completed: 0, failed: 0, total: 0 },
    setQueueStats: (queueStats) => set({ queueStats }),
    isProcessing: false,
    setIsProcessing: (isProcessing) => set({ isProcessing }),
    ebayStatus: 'checking',
    setEbayStatus: (ebayStatus) => set({ ebayStatus }),

    // Logs
    jobLogs: {},
    setJobLogs: (jobLogs) => set({ jobLogs }),
    addLog: (jobId, log) => set((state) => {
        const logs = state.jobLogs[jobId] || []
        return {
            jobLogs: {
                ...state.jobLogs,
                [jobId]: [...logs, log].slice(-100)
            }
        }
    }),

    // Scanning State
    isScanning: false,
    setIsScanning: (isScanning) => set({ isScanning }),
    scanMessage: null,
    setScanMessage: (scanMessage) => set({ scanMessage }),

    // Actions
    handleStart: async () => {
        try {
            await startQueue()
            toast.success('Queue started')
        } catch (err) {
            console.error(err)
            toast.error('Failed to start queue')
        }
    },

    handlePause: async () => {
        try {
            await pauseQueue()
            toast.info('Queue paused')
        } catch (err) {
            console.error(err)
            toast.error('Failed to pause queue')
        }
    },

    handleScan: async () => {
        set({ isScanning: true, scanMessage: null })
        try {
            const result = await scanInbox()
            if (result.success) {
                set({ scanMessage: `${result.added} new folders queued!` })
                toast.success(`Scan complete — ${result.added} new items`)
                const jobsData = await fetchJobs()
                set({ jobs: jobsData })
                if (jobsData.length > 0 && !get().selectedJob) {
                    set({ selectedJob: jobsData[0] })
                }
            } else {
                set({ scanMessage: 'Scan failed' })
                toast.error('Scan failed')
            }
        } catch {
            set({ scanMessage: 'Scan error' })
            toast.error('Scan error — is the backend running?')
        } finally {
            set({ isScanning: false })
            setTimeout(() => set({ scanMessage: null }), 3000)
        }
    },


    fetchPending: async () => {
        try {
            const listings = await fetchPendingListings()
            set({ pendingListings: listings })
        } catch (err) {
            console.error(err)
            toast.error('Failed to fetch pending listings')
        }
    },

    updatePending: async (id, updates) => {
        try {
            await quickEditListing(id, updates)
            set((state) => ({
                pendingListings: state.pendingListings.map(l =>
                    l.id === id ? { ...l, ...updates } : l
                )
            }))
            toast.success('Listing updated')
        } catch (err) {
            console.error(err)
            toast.error('Update failed')
        }
    },

    approvePending: async (ids) => {
        try {
            const result = await approvePendingListings(ids)
            if (result.success) {
                toast.success(`Approved ${result.approved_count} listings`)
                set((state) => ({
                    pendingListings: state.pendingListings.filter(l => !ids.includes(l.id))
                }))
                // Refresh main jobs list
                const jobsData = await fetchJobs()
                set({ jobs: jobsData })
            }
        } catch (err) {
            console.error(err)
            toast.error('Approval failed')
        }
    },

    deletePending: async (id, deleteFolder = true) => {
        try {
            await deleteJob(id, deleteFolder)
            set((state) => ({
                pendingListings: state.pendingListings.filter(l => l.id !== id)
            }))
            // Also refresh main jobs list in case it affects dashboard
            const jobsData = await fetchJobs()
            set({ jobs: jobsData })
            toast.success('Listing deleted')
        } catch (err) {
            console.error(err)
            toast.error('Delete failed')
        }
    },

    // Filtering & UI
    activeFilter: 'all',
    setActiveFilter: (activeFilter) => set({ activeFilter }),
    batchSummary: null,
    setBatchSummary: (batchSummary) => set({ batchSummary }),
}))
