import { useState } from 'react'
import { AnalyticsDashboard } from '@/components/AnalyticsDashboard'
import { ActiveListings } from '@/components/ActiveListings'
import { Sidebar } from '@/components/Sidebar'
import { Settings } from '@/pages/Settings'
import { Dashboard } from '@/pages/Dashboard'
import { QuickListingForm } from '@/components/QuickListingForm'
import { Toaster } from '@/components/ui/sonner'
import { PWAInstallBanner } from '@/components/PWAInstallBanner'
import { MobileNavBar } from '@/components/MobileNavBar'
import { PullToRefreshIndicator } from '@/components/PullToRefreshIndicator'
import { usePullToRefresh } from '@/hooks/usePullToRefresh'

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')

  // Pull-to-refresh functionality for mobile
  const { isRefreshing, pullDistance } = usePullToRefresh({
    onRefresh: async () => {
      console.log('Refreshing...', activeTab)
      await new Promise(resolve => setTimeout(resolve, 1000))
      window.location.reload()
    },
    threshold: 80,
  })

  return (
    <div className="flex h-screen bg-stone-50">
      {/* Pull-to-refresh indicator */}
      <PullToRefreshIndicator
        pullDistance={pullDistance}
        isRefreshing={isRefreshing}
      />

      {/* Desktop Sidebar - hidden on mobile */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} className="hidden md:block" />

      {/* Main Content - add bottom padding on mobile for nav bar */}
      <main className="flex-1 overflow-hidden pb-16 md:pb-0">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'create' && <QuickListingForm />}
        {activeTab === 'inventory' && <ActiveListings />}
        {activeTab === 'analytics' && <AnalyticsDashboard />}
        {activeTab === 'settings' && <Settings />}
      </main>

      {/* Mobile Bottom Navigation */}
      <MobileNavBar activeTab={activeTab} onTabChange={setActiveTab} />

      <Toaster position="bottom-right" richColors />
      <PWAInstallBanner />
    </div>
  )
}

export default App
