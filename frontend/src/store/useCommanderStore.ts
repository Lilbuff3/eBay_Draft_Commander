import { create } from 'zustand'
import { type Job, type QueueStats, startQueue, pauseQueue, scanInbox, fetchJobs } from '@/lib/api'
import { type LogEntry } from '@/components/LogViewer'
import { toast } from 'sonner'

interface CommanderState {
    // Navigation
    activeTab: string
    setActiveTab: (tab: string) => void

    // Job Data
    jobs: Job[]
    setJobs: (jobs: Job[]) => void
    selectedJob: Job | null
    setSelectedJob: (job: Job | null) => void

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
    refreshData: () => Promise<void>
}

export const useCommanderStore = create<CommanderState>((set, get) => ({
    // Navigation
    activeTab: localStorage.getItem('activeTab') || 'dashboard',
    setActiveTab: (tab) => {
        localStorage.setItem('activeTab', tab)
        set({ activeTab: tab })
    },

    // Job Data
    jobs: [],
    setJobs: (jobs) => set({ jobs }),
    selectedJob: null,
    setSelectedJob: (job) => set({ selectedJob: job }),

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

    refreshData: async () => {
        // This will be triggered via refetch in useJobSync but we can expose a trigger here
        // Actually, it's better to just invalidate queries if we use react-query
    }
}))
