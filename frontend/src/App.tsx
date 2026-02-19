import { useState, useEffect } from 'react'
import { AnalyticsDashboard } from '@/components/AnalyticsDashboard'
import { ActiveListings } from '@/components/ActiveListings'
import { Sidebar } from '@/components/Sidebar'
import { Settings } from '@/pages/Settings'
import { Dashboard } from '@/pages/Dashboard'
import { BatchScan } from '@/pages/BatchScan'
import { QuickListingForm } from '@/components/QuickListingForm'
import { Toaster } from '@/components/ui/sonner'
import { PWAInstallBanner } from '@/components/PWAInstallBanner'
import { MobileNavBar } from '@/components/MobileNavBar'
import { PullToRefreshIndicator } from '@/components/PullToRefreshIndicator'
// import { usePullToRefresh } from '@/hooks/usePullToRefresh'
import { PhotoEditor } from '@/components/PhotoEditor'
import { PriceResearch } from '@/components/PriceResearch'
import { TemplateManager } from '@/components/TemplateManager'
import { PreviewPanel } from '@/components/PreviewPanel'
import { fetchJobs, fetchStatus, startQueue, pauseQueue, scanInbox, type Job, type QueueStats } from '@/lib/api'
import { io } from 'socket.io-client'
import type { LogEntry } from '@/components/LogViewer'

export default function App() {
  const [activeTab, setActiveTab] = useState(() => {
    return localStorage.getItem('activeTab') || 'dashboard'
  })

  // Persist Tab
  useEffect(() => {
    localStorage.setItem('activeTab', activeTab)
  }, [activeTab])

  // Global State
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [queueStats, setQueueStats] = useState<QueueStats>({ pending: 0, completed: 0, failed: 0, total: 0 })
  const [isProcessing, setIsProcessing] = useState(false)
  const [ebayStatus, setEbayStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking')
  const [isScanning, setIsScanning] = useState(false)
  const [scanMessage, setScanMessage] = useState<string | null>(null)
  const [jobLogs, setJobLogs] = useState<Record<string, LogEntry[]>>({})

  // Initial fetch and Realtime (Socket.IO) setup
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [jobsData, statusData] = await Promise.all([
          fetchJobs(),
          fetchStatus()
        ])
        setJobs(jobsData)
        setQueueStats(statusData.stats)
        setIsProcessing(statusData.status === 'processing')
      } catch (err) {
        console.error('Fetch error:', err)
      }
    }

    const checkEbay = async () => {
      try {
        const res = await fetch('/api/ebay/status')
        const data = await res.json()
        setEbayStatus(data.status === 'connected' ? 'connected' : 'disconnected')
      } catch {
        setEbayStatus('disconnected')
      }
    }

    // Initial load
    fetchData()
    checkEbay()

    // Socket.IO Connection
    const socketUrl = import.meta.env.DEV ? '/' : 'http://127.0.0.1:5000'
    const socket = io(socketUrl)

    socket.on('connect', () => {
      console.log('Connected to Event Bus ⚡')
    })

    socket.on('job_added', (newJob: Job) => {
      setJobs(prev => [...prev, newJob])
    })

    socket.on('job_update', (updatedJob: Job) => {
      setJobs(prev => prev.map(j => j.id === updatedJob.id ? updatedJob : j))
      // Update stats if status changed
      fetchStatus().then(data => setQueueStats(data.stats))
    })

    socket.on('job_log', (log: unknown) => {
      setJobLogs(prev => {
        const entry = log as LogEntry
        const jobId = entry.job_id
        const currentLogs = prev[jobId] || []
        const newLogs = [...currentLogs, entry].slice(-100)
        return {
          ...prev,
          [jobId]: newLogs
        }
      })
    })

    const ebayInterval = setInterval(checkEbay, 60000)

    return () => {
      socket.off('job_added')
      socket.off('job_update')
      socket.off('job_log')
      socket.disconnect()
      clearInterval(ebayInterval)
    }
  }, [])

  // Global Actions
  const handleStart = async () => {
    try {
      await startQueue()
      setIsProcessing(true)
    } catch (_e) {
      console.error(_e)
    }
  }

  const handlePause = async () => {
    try {
      await pauseQueue()
      setIsProcessing(false)
    } catch (err) {
      console.error(err)
    }
  }

  const handleScan = async () => {
    setIsScanning(true)
    setScanMessage(null)
    try {
      const result = await scanInbox()
      if (result.success) {
        setScanMessage(`${result.added} new folders queued!`)
        // Fetch will happen via realtime or manual re-fetch
        const jobsData = await fetchJobs()
        setJobs(jobsData)
        if (jobsData.length > 0 && !selectedJob) {
          setSelectedJob(jobsData[0])
        }
      } else {
        setScanMessage('Scan failed')
      }
    } catch {
      setScanMessage('Scan error')
    } finally {
      setIsScanning(false)
      setTimeout(() => setScanMessage(null), 3000)
    }
  }

  // Pull-to-refresh functionality for mobile
  /*
  const { isRefreshing, pullDistance } = usePullToRefresh({
    onRefresh: async () => {
      console.log('Refreshing...', activeTab)
      await new Promise(resolve => setTimeout(resolve, 1000))
      window.location.reload()
    },
    threshold: 80,
  })
  */
  const isRefreshing = false;
  const pullDistance = 0;

  return (
    <div className="flex h-screen bg-stone-50">
      {/* Pull-to-refresh indicator */}
      <PullToRefreshIndicator
        pullDistance={pullDistance}
        isRefreshing={isRefreshing}
      />

      {/* Desktop Sidebar */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} className="hidden md:block" />

      {/* Main Content */}
      <main className="flex-1 overflow-auto pb-16 md:pb-0 relative">
        {activeTab === 'dashboard' && (
          <Dashboard
            jobs={jobs}
            selectedJob={selectedJob}
            setSelectedJob={setSelectedJob}
            setJobs={setJobs}
            queueStats={queueStats}
            isProcessing={isProcessing}
            ebayStatus={ebayStatus}
            handleStart={handleStart}
            handlePause={handlePause}
            handleScan={handleScan}
            isScanning={isScanning}
            scanMessage={scanMessage}
            jobLogs={jobLogs}
          />
        )}

        {activeTab === 'create' && <QuickListingForm />}

        {activeTab === 'batch-scan' && (
          <div className="h-full p-6 overflow-hidden">
            <BatchScan />
          </div>
        )}

        {/* Tools lifted to top level */}
        {activeTab === 'photo-editor' && (
          <div className="h-full p-6 overflow-hidden">
            <PhotoEditor
              jobId={selectedJob?.id}
              onClose={() => setActiveTab('dashboard')}
            />
          </div>
        )}
        {activeTab === 'price-research' && (
          <div className="h-full p-6 overflow-hidden">
            <PriceResearch
              jobId={selectedJob?.id}
              initialQuery={selectedJob?.name}
              onClose={() => setActiveTab('dashboard')}
            />
          </div>
        )}
        {activeTab === 'templates' && (
          <div className="h-full p-6 overflow-hidden">
            <TemplateManager onClose={() => setActiveTab('dashboard')} />
          </div>
        )}
        {activeTab === 'preview' && (
          <div className="h-full p-6 overflow-hidden">
            <PreviewPanel
              jobId={selectedJob?.id}
              onClose={() => setActiveTab('dashboard')}
            />
          </div>
        )}

        {/* Business Tools */}
        {activeTab === 'inventory' && <ActiveListings />}
        {activeTab === 'analytics' && <AnalyticsDashboard />}
        {activeTab === 'settings' && <Settings />}
      </main>

      {/* Mobile Bottom Navigation - todo: update to support new tab structure if needed */}
      <MobileNavBar activeTab={activeTab} onTabChange={setActiveTab} />

      <Toaster position="bottom-right" richColors />
      <PWAInstallBanner />
    </div>
  )
}


