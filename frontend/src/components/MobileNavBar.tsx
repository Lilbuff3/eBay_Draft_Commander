import { LayoutTemplate, Package, BarChart3, Settings, ScanLine } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useHaptics } from '@/hooks/useHaptics'

const leftTabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutTemplate },
    { id: 'inventory', label: 'Inventory', icon: Package },
]
const rightTabs = [
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Settings },
]

export function MobileNavBar() {
    const activeTab = useCommanderStore(state => state.activeTab)
    const onTabChange = useCommanderStore(state => state.setActiveTab)
    const handleScan = useCommanderStore(state => state.handleScan)
    const { tap } = useHaptics()

    const handleTabChange = (tabId: string) => {
        if (tabId !== activeTab) {
            tap()
            onTabChange(tabId)
        }
    }

    const onAIClick = () => {
        tap()
        handleScan()
    }

    const renderTab = (tab: {id: string, label: string, icon: any}) => {
        const isActive = activeTab === tab.id
        return (
            <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                aria-label={tab.label}
                aria-current={isActive ? 'page' : undefined}
                className="flex flex-col items-center justify-center gap-1 w-[60px] h-full min-h-[44px] transition-transform hover:scale-110 focus-visible:outline-none"
            >
                <tab.icon
                    size={22}
                    strokeWidth={isActive ? 2.5 : 2}
                    className={cn(
                        "transition duration-300",
                        isActive ? "text-brand-400" : "text-slate-500"
                    )}
                />
                <span
                    className={cn(
                        "text-[10px] font-medium transition duration-300",
                        isActive ? "text-brand-400" : "text-slate-500"
                    )}
                >
                    {tab.label}
                </span>
            </button>
        )
    }

    return (
        <nav className="fixed bottom-0 left-0 right-0 md:hidden z-50">
            {/* Glassmorphic Nav */}
            <div className="bg-slate-950/80 backdrop-blur-2xl border-t border-slate-800/60 pb-safe">
                <div className="flex items-start justify-between h-[80px] px-4 pt-4 relative">
                    
                    {leftTabs.map(renderTab)}

                    {/* Central AI Button */}
                    <div className="relative -top-8 flex flex-col items-center group" onClick={onAIClick}>
                        <div className="w-16 h-16 bg-gradient-to-br from-brand-400 to-brand-600 rounded-full flex items-center justify-center shadow-glow-lg group-hover:scale-105 transition-transform z-10 border-4 border-slate-950 cursor-pointer">
                            <ScanLine className="text-white w-7 h-7" strokeWidth={2.5} />
                        </div>
                        {/* Outer glow ring */}
                        <div className="absolute inset-0 top-1 bg-brand-500 rounded-full blur-xl opacity-50 group-hover:opacity-80 transition-opacity animate-pulse z-0 pointer-events-none"></div>
                    </div>

                    {rightTabs.map(renderTab)}
                </div>
            </div>
        </nav>
    )
}
