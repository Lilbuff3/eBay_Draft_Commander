import { useState, useEffect, useRef, useCallback } from 'react'
import { fetchJobs, fetchStatus, type Job, type QueueStatus, type JobStatus } from '@/lib/api'
import { io, type Socket } from 'socket.io-client'
import { toast } from 'sonner'
import type { LogEntry } from '@/components/LogViewer'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCommanderStore } from '@/store/useCommanderStore'

/**
 * Custom hook that encapsulates all Socket.IO real-time sync logic
 * and caching fallback for the job queue.
 *
 * Refactored to use React Query and synchronized with Zustand store.
 */
export function useJobSync() {
    const queryClient = useQueryClient()
    const socketRef = useRef<Socket | null>(null)
    const [isSocketConnected, setIsSocketConnected] = useState(false)

    // Store Actions
    const storeSetJobs = useCommanderStore(state => state.setJobs)
    const setQueueStats = useCommanderStore(state => state.setQueueStats)
    const setIsProcessing = useCommanderStore(state => state.setIsProcessing)
    const setEbayStatus = useCommanderStore(state => state.setEbayStatus)
    const addLog = useCommanderStore(state => state.addLog)

    // 1. Fetch Jobs directly with React Query
    const { data: jobs = [], refetch: refetchJobs } = useQuery({
        queryKey: ['jobs'],
        queryFn: fetchJobs,
        initialData: [] as Job[],
        refetchInterval: isSocketConnected ? false : 5000,
    })

    // Sync React Query data → Zustand store (stable ref from initialData prevents infinite loops)
    const prevJobsRef = useRef(jobs)
    useEffect(() => {
        if (prevJobsRef.current !== jobs) {
            prevJobsRef.current = jobs
            storeSetJobs(jobs)
        }
    }, [jobs, storeSetJobs])

    // 2. We expose a setJobs wrapper so existing components can optimistically update
    const setJobs = useCallback((newJobsOrUpdater: Job[] | ((prev: Job[]) => Job[])) => {
        queryClient.setQueryData(['jobs'], (old: Job[] | undefined) => {
            let next: Job[]
            if (typeof newJobsOrUpdater === 'function') {
                next = newJobsOrUpdater(old || [])
            } else {
                next = newJobsOrUpdater
            }
            return next
        })
    }, [queryClient])

    // 3. Queue status and stats
    const { data: statusData, refetch: refetchStatus } = useQuery({
        queryKey: ['status'],
        queryFn: fetchStatus,
        initialData: { status: 'idle', stats: { pending: 0, completed: 0, failed: 0, total: 0 }, current_job: null, progress: { current: 0, total: 0, percent: 0 } } as QueueStatus,
        refetchInterval: isSocketConnected ? false : 5000,
    })

    useEffect(() => {
        if (statusData) {
            setQueueStats(statusData.stats)
            setIsProcessing(statusData.status === 'processing')
        }
    }, [statusData, setQueueStats, setIsProcessing])

    // 4. eBay status polling
    const { data: ebayStatusObj } = useQuery({
        queryKey: ['ebayStatus'],
        queryFn: async () => {
            try {
                const res = await fetch('/api/ebay/status')
                const data = await res.json()
                return data.status === 'connected' ? 'connected' as const : 'disconnected' as const
            } catch {
                return 'disconnected' as const
            }
        },
        refetchInterval: 60000,
        initialData: 'checking' as const
    })

    useEffect(() => {
        setEbayStatus(ebayStatusObj)
    }, [ebayStatusObj, setEbayStatus])

    const refreshData = useCallback(async () => {
        await Promise.all([
            refetchJobs(),
            refetchStatus()
        ])
    }, [refetchJobs, refetchStatus])

    // 5. Socket.IO Event Bus
    useEffect(() => {
        const socket = io('/', {
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 10000,
        })
        socketRef.current = socket

        socket.on('connect', () => {
            console.log('Connected to Event Bus ⚡')
            setIsSocketConnected(true)
            refreshData()
        })

        socket.on('disconnect', (reason: string) => {
            console.warn('Socket.IO disconnected:', reason)
            setIsSocketConnected(false)
            toast.warning('Live updates disconnected — switching to polling mode')
        })

        socket.on('reconnect_failed', () => {
            toast.error('Unable to reconnect to server')
        })

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const formatJobPayload = (rawJob: any): Job => {
            const aiData = rawJob.ai_data || {}
            const listing = aiData.listing || {}
            const displayName = rawJob.user_title || listing.suggested_title || aiData.seo_title || rawJob.folder_name

            return {
                id: String(rawJob.id),
                name: String(rawJob.folder_name),
                display_name: displayName,
                status: rawJob.status as JobStatus,
                folder_path: rawJob.folder_path,
                listing_id: rawJob.listing_id || null,
                offer_id: rawJob.offer_id || null,
                price: rawJob.price || null,
                error_type: rawJob.error_type || null,
                error_message: rawJob.error_message || null,
                started_at: rawJob.started_at || null,
                completed_at: rawJob.completed_at || null,
                thumbnail_name: rawJob.thumbnail_name || null,
                thumbnail_url: rawJob.thumbnail_name ? `/api/job/${rawJob.id}/image/${rawJob.thumbnail_name}` : null,
                condition: rawJob.condition || (rawJob.job_metadata?.condition) || null,
                scheduled_time: rawJob.scheduled_time || null,
                confidence_score: rawJob.confidence_score || null
            }
        }

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        socket.on('job_added', (rawJob: any) => {
            if (rawJob) {
                const newJob = formatJobPayload(rawJob)
                queryClient.setQueryData(['jobs'], (old: Job[] | undefined) => {
                    if (!old) return [newJob]
                    if (old.some(j => j.id === newJob.id)) return old
                    return [...old, newJob]
                })
            } else {
                queryClient.invalidateQueries({ queryKey: ['jobs'] })
            }
            queryClient.invalidateQueries({ queryKey: ['status'] })
        })

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        socket.on('job_update', (rawJob: any) => {
            if (rawJob) {
                const updatedJob = formatJobPayload(rawJob)
                queryClient.setQueryData(['jobs'], (old: Job[] | undefined) => {
                    if (!old) return [updatedJob]
                    return old.map(job => job.id === updatedJob.id ? { ...job, ...updatedJob } : job)
                })
            } else {
                queryClient.invalidateQueries({ queryKey: ['jobs'] })
            }
            queryClient.invalidateQueries({ queryKey: ['status'] })
        })

        socket.on('job_log', (log: unknown) => {
            const entry = log as LogEntry
            addLog(entry.job_id, entry)
        })

        socket.on('batch_complete', (summary: {
            succeeded: number;
            failed: number;
            total_value: number;
            avg_time: number;
            total_duration: number;
        }) => {
            console.log('Batch complete:', summary)
            useCommanderStore.getState().setBatchSummary(summary)
            toast.success(`Batch Processed: ${summary.succeeded} succeeded, ${summary.failed} failed`, {
                description: `Total Value: $${summary.total_value.toFixed(2)} | Avg Time: ${summary.avg_time}s`,
                duration: 15000,
            })
        })

        return () => {
            socket.off('connect')
            socket.off('disconnect')
            socket.off('reconnect_failed')
            socket.off('job_added')
            socket.off('job_update')
            socket.off('job_log')
            socket.off('batch_complete')
            socket.disconnect()
        }
    }, [queryClient, refreshData, addLog])

    return {
        refreshData,
        setJobs // Still exposed for optimistic updates if needed
    }
}
