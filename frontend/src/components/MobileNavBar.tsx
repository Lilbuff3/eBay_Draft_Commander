import { LayoutTemplate, ShieldCheck, Package, BarChart3, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useHaptics } from '@/hooks/useHaptics'

const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutTemplate },
    { id: 'review', label: 'Review', icon: ShieldCheck },
    { id: 'inventory', label: 'Inventory', icon: Package },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Settings },
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

    return (
        <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-stone-200 md:hidden z-50">
            <div className="flex items-center justify-around h-16 pb-safe px-2">
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => handleTabChange(tab.id)}
                        className={cn(
                            "flex flex-col items-center justify-center gap-1 w-full h-full min-h-[44px] transition-colors duration-200",
                            activeTab === tab.id ? "text-sage-600" : "text-stone-400"
                        )}
                    >
                        <tab.icon size={22} strokeWidth={activeTab === tab.id ? 2.5 : 2} />
                        <span className="text-[10px] font-bold uppercase tracking-tight">{tab.label}</span>
                    </button>
                ))}
            </div>
        </nav>
    )
}
