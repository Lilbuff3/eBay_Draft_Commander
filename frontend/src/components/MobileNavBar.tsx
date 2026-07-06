import { LayoutTemplate, Package, BookOpen, ShoppingBag, ScanBarcode, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useHaptics } from '@/hooks/useHaptics'

const tabs = [
    { id: 'dashboard', label: 'Home', icon: LayoutTemplate },
    { id: 'inventory', label: 'Inventory', icon: Package },
    { id: 'sourcing', label: 'Source', icon: ScanBarcode },
    { id: 'batch-scan', label: 'Books', icon: BookOpen },
    { id: 'orders', label: 'Orders', icon: ShoppingBag },
]

export function MobileNavBar() {
    const activeTab = useCommanderStore(state => state.activeTab)
    const onTabChange = useCommanderStore(state => state.setActiveTab)
    const { tap } = useHaptics()

    const handleTabChange = (tabId: string) => {
        if (tabId !== activeTab) {
            tap()
            onTabChange(tabId)
        }
    }

    const renderTab = (tab: {id: string, label: string, icon: LucideIcon}) => {
        const isActive = activeTab === tab.id
        return (
            <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                aria-label={tab.label}
                aria-current={isActive ? 'page' : undefined}
                className="flex flex-col items-center justify-center gap-1 w-[56px] h-full min-h-[44px] transition-transform hover:scale-105 focus-visible:outline-none"
            >
                <tab.icon
                    size={20}
                    strokeWidth={isActive ? 2.5 : 2}
                    className={cn(
                        "transition duration-300",
                        isActive ? "text-brand-400" : "text-slate-500"
                    )}
                />
                <span
                    className={cn(
                        "text-[9.5px] font-semibold tracking-tight transition duration-300",
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
                <div className="flex items-center justify-around h-[64px] px-2 relative">
                    {tabs.map(renderTab)}
                </div>
            </div>
        </nav>
    )
}
