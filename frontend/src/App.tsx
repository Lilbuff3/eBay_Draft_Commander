import { lazy, Suspense, useEffect, useMemo } from 'react'
import { AnimatePresence, motion, MotionConfig } from 'framer-motion'
import { Loader2 } from 'lucide-react'
// Eager: app chrome + the landing tab (Dashboard). Everything else is a tab
// body loaded on demand so recharts/dnd-kit/etc. stay off the cold-load path.
import { Sidebar } from '@/components/Sidebar'
import { useCommanderStore } from '@/store/useCommanderStore'
import { Dashboard } from '@/pages/Dashboard'
import { MobileNavBar } from '@/components/MobileNavBar'
import { MobileUploadFAB } from '@/components/MobileUploadFAB'
import { ApiKeyDialog } from '@/components/ApiKeyDialog'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { Toaster, toast } from 'sonner'
import { InstallPrompt } from '@/components/InstallPrompt'
import { OfflineIndicator } from '@/components/OfflineIndicator'
import { useJobSync } from '@/hooks/useJobSync'
import { useIsMobile } from '@/hooks/useIsMobile'
import { onUpdateAvailable } from '@/lib/pwa'

// Lazy tab bodies (named exports → default-wrap for React.lazy).
const ActiveListings = lazy(() => import('@/components/ActiveListings').then(m => ({ default: m.ActiveListings })))
const Settings = lazy(() => import('@/pages/Settings').then(m => ({ default: m.Settings })))
const Orders = lazy(() => import('@/pages/Orders').then(m => ({ default: m.Orders })))
const BatchScan = lazy(() => import('@/pages/BatchScan').then(m => ({ default: m.BatchScan })))
const Sourcing = lazy(() => import('@/pages/Sourcing').then(m => ({ default: m.Sourcing })))
const ReviewQueue = lazy(() => import('@/components/listings/ReviewQueue').then(m => ({ default: m.ReviewQueue })))
const Profit = lazy(() => import('@/pages/Profit').then(m => ({ default: m.Profit })))

function PageLoader() {
  return (
    <div className="flex h-full items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-stone-400" />
    </div>
  )
}

// Tab ordering for directional transitions
const TAB_ORDER = ['dashboard', 'orders', 'review', 'profit', 'inventory', 'batch-scan', 'sourcing', 'settings']

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
  const isMobile = useIsMobile()

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

  // PWA: auto-reload onto the newest build (no manual "Reload" tap).
  // Fires at most ONCE per tab session — the sessionStorage guard is a hard
  // backstop against reload loops (a controllerchange-based reload can tight-loop
  // if the SW keeps re-detecting an update). After the one reload the user is on
  // the latest build; a second update in the same session waits for next launch.
  useEffect(() => {
    onUpdateAvailable(() => {
      if (sessionStorage.getItem('dc-pwa-updated')) return
      sessionStorage.setItem('dc-pwa-updated', '1')
      toast('Updating to the latest version…', { id: 'pwa-update', duration: 2500 })
      setTimeout(() => window.location.reload(), 1200)
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
    <div className="dark flex h-screen bg-[#05050A] text-slate-100 relative">
      <OfflineIndicator />

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
              <Suspense fallback={<PageLoader />}>
              {activeTab === 'dashboard' && <Dashboard />}

              {activeTab === 'batch-scan' && (
                <div className="h-full p-6 overflow-hidden">
                  <BatchScan />
                </div>
              )}

              {activeTab === 'sourcing' && <Sourcing />}

              {/* Business Tools */}
              {activeTab === 'orders' && <Orders />}
              {activeTab === 'profit' && <Profit />}
              {activeTab === 'inventory' && <ActiveListings />}
              {activeTab === 'review' && <ReviewQueue />}
              {activeTab === 'settings' && <Settings />}
              </Suspense>
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
      <ApiKeyDialog />
      <InstallPrompt />
    </div>
    </MotionConfig>
  )
}
