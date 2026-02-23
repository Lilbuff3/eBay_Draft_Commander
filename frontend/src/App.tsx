import { useEffect } from 'react'
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
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { Toaster } from 'sonner'
import { PullToRefreshIndicator } from '@/components/PullToRefreshIndicator'
import { PWAInstallBanner } from '@/components/PWAInstallBanner'
import { useJobSync } from '@/hooks/useJobSync'

export default function App() {
  const activeTab = useCommanderStore(state => state.activeTab)
  const setActiveTab = useCommanderStore(state => state.setActiveTab)
  const selectedJob = useCommanderStore(state => state.selectedJob)

  // Real-time job sync initialization
  useJobSync()

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
      <PullToRefreshIndicator pullDistance={0} isRefreshing={false} />

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
          {activeTab === 'analytics' && <AnalyticsDashboard />}
          {activeTab === 'settings' && <Settings />}
        </ErrorBoundary>
      </main>

      {/* Mobile Bottom Navigation */}
      <MobileNavBar />

      <Toaster position={window.innerWidth < 768 ? "top-center" : "bottom-right"} richColors />
      <PWAInstallBanner />
    </div>
  )
}
