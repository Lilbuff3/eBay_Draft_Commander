import { useEffect, useCallback } from 'react'
import { AnalyticsDashboard } from '@/components/AnalyticsDashboard'
import { ActiveListings } from '@/components/ActiveListings'
import { Sidebar } from '@/components/Sidebar'
import { useCommanderStore } from '@/store/useCommanderStore'
import { Settings } from '@/pages/Settings'
import { Dashboard } from '@/pages/Dashboard'
import { BatchScan } from '@/pages/BatchScan'
import { QuickListingForm } from '@/components/QuickListingForm'
import { PhotoEditor } from '@/components/PhotoEditor'
import { PriceResearch } from '@/components/PriceResearch'
import { TemplateManager } from '@/components/TemplateManager'
import { PreviewPanel } from '@/components/PreviewPanel'
import { MobileNavBar } from '@/components/MobileNavBar'
import { MobileUploadFAB } from '@/components/MobileUploadFAB'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { Toaster } from 'sonner'
import { PullToRefreshIndicator } from '@/components/PullToRefreshIndicator'
import { InstallPrompt } from '@/components/InstallPrompt'
import { ReviewQueue } from '@/components/listings/ReviewQueue'
import { useJobSync } from '@/hooks/useJobSync'
import { usePullToRefresh } from '@/hooks/usePullToRefresh'

export default function App() {
  const activeTab = useCommanderStore(state => state.activeTab)
  const setActiveTab = useCommanderStore(state => state.setActiveTab)
  const selectedJob = useCommanderStore(state => state.selectedJob)

  // Real-time job sync initialization
  const { refreshData } = useJobSync()

  // Pull-to-refresh on mobile
  const { pullDistance, isRefreshing } = usePullToRefresh({
    onRefresh: useCallback(async () => {
      await refreshData()
    }, [refreshData]),
    isEnabled: activeTab === 'dashboard',
  })

  // Android back button handling
  useEffect(() => {
    const handlePopState = () => {
      if (activeTab !== 'dashboard') {
        setActiveTab('dashboard')
      }
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [activeTab, setActiveTab])

  // Push history state on tab changes
  useEffect(() => {
    if (activeTab !== 'dashboard') {
      window.history.pushState({ tab: activeTab }, '', '')
    }
  }, [activeTab])

  return (
    <div className="flex h-screen bg-stone-50">
      <PullToRefreshIndicator pullDistance={pullDistance} isRefreshing={isRefreshing} />

      {/* Desktop Sidebar */}
      <Sidebar className="hidden md:block" />

      {/* Main Content */}
      <main className="flex-1 overflow-auto pb-16 md:pb-0 relative">
        <ErrorBoundary>
          {activeTab === 'dashboard' && <Dashboard />}

          {activeTab === 'create' && <QuickListingForm />}

          {activeTab === 'batch-scan' && (
            <div className="h-full p-6 overflow-hidden">
              <BatchScan />
            </div>
          )}

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
          {activeTab === 'review' && <ReviewQueue />}
          {activeTab === 'analytics' && <AnalyticsDashboard />}
          {activeTab === 'settings' && <Settings />}
        </ErrorBoundary>
      </main>

      {/* Mobile Upload FAB — only on dashboard tab */}
      {activeTab === 'dashboard' && (
        <MobileUploadFAB
          onFilesSelected={(files) => {
            // Trigger upload via the same mechanism as UploadZone
            const formData = new FormData()
            Array.from(files).forEach(f => formData.append('files', f))
            fetch('/api/upload', { method: 'POST', body: formData })
              .then(res => res.json())
              .then(data => {
                if (data.job_id) {
                  console.log('Upload started, job:', data.job_id)
                }
              })
              .catch(err => console.error('Upload failed:', err))
          }}
        />
      )}

      {/* Mobile Bottom Navigation */}
      <MobileNavBar />

      <Toaster position={window.innerWidth < 768 ? "top-center" : "bottom-right"} richColors />
      <InstallPrompt />
    </div>
  )
}
