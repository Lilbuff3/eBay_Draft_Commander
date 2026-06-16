import { useEffect, useCallback, useMemo } from 'react'
import { AnimatePresence, motion, MotionConfig } from 'framer-motion'
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
import { Toaster, toast } from 'sonner'
import { PullToRefreshIndicator } from '@/components/PullToRefreshIndicator'
import { InstallPrompt } from '@/components/InstallPrompt'
import { OfflineIndicator } from '@/components/OfflineIndicator'
import { ReviewQueue } from '@/components/listings/ReviewQueue'
import { useJobSync } from '@/hooks/useJobSync'
import { usePullToRefresh } from '@/hooks/usePullToRefresh'
import { useIsMobile } from '@/hooks/useIsMobile'
import { onUpdateAvailable } from '@/lib/pwa'

// Tab ordering for directional transitions
const TAB_ORDER = ['dashboard', 'review', 'inventory', 'analytics', 'settings']

function getTabIndex(tab: string): number {
  const idx = TAB_ORDER.indexOf(tab)
  return idx === -1 ? TAB_ORDER.length : idx // secondary tabs treated as "rightmost"
}

// MD3 Expressive easing — module-level constant (no re-allocation)
const PAGE_TRANSITION = {
  type: 'tween' as const,
  ease: [0.2, 0, 0, 1] as [number, number, number, number],
  duration: 0.25,
}

export default function App() {
  const activeTab = useCommanderStore(state => state.activeTab)
  const previousTab = useCommanderStore(state => state.previousTab)
  const setActiveTab = useCommanderStore(state => state.setActiveTab)
  const selectedJob = useCommanderStore(state => state.selectedJob)
  const isMobile = useIsMobile()

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

  // PWA update notification
  useEffect(() => {
    onUpdateAvailable(() => {
      toast('Update available', {
        id: 'pwa-update',
        description: 'A new version of Draft Commander is ready.',
        duration: Infinity,
        action: {
          label: 'Reload',
          onClick: () => window.location.reload(),
        },
      })
    })
  }, [])

  // Determine slide direction: positive = slide from right, negative = slide from left
  const direction = getTabIndex(activeTab) >= getTabIndex(previousTab) ? 1 : -1

  const pageVariants = useMemo(() => ({
    initial: (dir: number) => ({
      x: isMobile ? dir * 60 : 0,
      opacity: 0,
    }),
    animate: {
      x: 0,
      opacity: 1,
    },
    exit: (dir: number) => ({
      x: isMobile ? dir * -60 : 0,
      opacity: 0,
    }),
  }), [isMobile])

  return (
    <MotionConfig reducedMotion="user">
    <div className="flex h-screen bg-transparent">
      <OfflineIndicator />
      <PullToRefreshIndicator pullDistance={pullDistance} isRefreshing={isRefreshing} />

      {/* Desktop Sidebar */}
      <Sidebar className="hidden md:block" />

      {/* Main Content */}
      <main className="flex-1 overflow-auto pb-20 md:pb-0 relative">
        <ErrorBoundary>
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={activeTab}
              custom={direction}
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={PAGE_TRANSITION}
              className="h-full"
            >
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
            </motion.div>
          </AnimatePresence>
        </ErrorBoundary>
      </main>

      {/* Mobile Upload FAB — only on dashboard tab */}
      {activeTab === 'dashboard' && (
        <MobileUploadFAB
          onUploadComplete={(jobId) => {
            useCommanderStore.getState().setLastUploadedJobId(jobId)
          }}
        />
      )}

      {/* Mobile Bottom Navigation */}
      <MobileNavBar />

      <Toaster position={isMobile ? "top-center" : "bottom-right"} richColors />
      <InstallPrompt />
    </div>
    </MotionConfig>
  )
}
