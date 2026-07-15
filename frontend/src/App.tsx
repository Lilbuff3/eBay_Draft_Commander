import { lazy, Suspense, useEffect, useMemo, useRef } from 'react'
import { AnimatePresence, motion, MotionConfig } from 'framer-motion'
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

// Content-shaped rather than a bare spinner: a lazy tab arriving over a phone
// connection otherwise flashes an empty screen on every switch.
function PageLoader() {
  return (
    <div className="p-4 sm:p-6 flex flex-col gap-4 animate-pulse" aria-busy="true" aria-label="Loading">
      <div className="h-8 w-48 rounded-lg bg-stone-200" />
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="h-24 rounded-3xl bg-stone-200" />
        <div className="h-24 rounded-3xl bg-stone-200" />
        <div className="h-24 rounded-3xl bg-stone-200 hidden md:block" />
      </div>
      <div className="flex flex-col gap-3">
        <div className="h-20 rounded-3xl bg-stone-200" />
        <div className="h-20 rounded-3xl bg-stone-200" />
        <div className="h-20 rounded-3xl bg-stone-200" />
      </div>
    </div>
  )
}

// Tabs that already own the capture affordance, plus Settings.
const FAB_HIDDEN_TABS = new Set(['batch-scan', 'sourcing', 'settings'])

// Tab ordering for directional transitions. Mirrors the mobile bar's left-to-right
// order (Home · Review · Inventory · Orders · More) so a swipe animates the way the
// nav implies; the More-sheet tabs trail behind it.
const TAB_ORDER = ['dashboard', 'review', 'inventory', 'orders', 'sourcing', 'batch-scan', 'profit', 'settings']

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

  // Android back: go to the tab the popped entry names, not always the dashboard.
  // `skipPush` stops the resulting setActiveTab from pushing a fresh entry —
  // without it, back would re-push the tab it just left and never unwind.
  const skipPush = useRef(false)
  useEffect(() => {
    const handlePopState = (e: PopStateEvent) => {
      const tab = (e.state as { tab?: string } | null)?.tab
      skipPush.current = true
      setActiveTab(tab ?? 'dashboard')
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [setActiveTab])

  // One history entry per real tab change, tagged with the tab it represents.
  // The first run only stamps the current entry (activeTab is restored from
  // localStorage, so it isn't necessarily the dashboard).
  const mounted = useRef(false)
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true
      window.history.replaceState({ tab: activeTab }, '')
      return
    }
    if (skipPush.current) {
      skipPush.current = false
      return
    }
    window.history.pushState({ tab: activeTab }, '')
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
    <div className="flex h-screen bg-background text-foreground relative">
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

      {/* Mobile Upload FAB. Available everywhere except the tabs that are
          themselves capture surfaces (Books/Source scan barcodes) and Settings,
          where a floating "new listing" button is just in the way. */}
      {!FAB_HIDDEN_TABS.has(activeTab) && (
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
