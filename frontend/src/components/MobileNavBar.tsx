import { LayoutTemplate, Package, BarChart3, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useHaptics } from '@/hooks/useHaptics'

const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutTemplate },
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
        <nav className="fixed bottom-0 left-0 right-0 md:hidden z-50">
            {/* Warm paper surface with elevation tint */}
            <div className="bg-paper/95 backdrop-blur-lg border-t border-stone-200/70">
                <div className="flex items-center justify-around h-[68px] pb-safe px-1">
                    {tabs.map((tab) => {
                        const isActive = activeTab === tab.id
                        return (
                            <button
                                key={tab.id}
                                onClick={() => handleTabChange(tab.id)}
                                aria-label={tab.label}
                                aria-current={isActive ? 'page' : undefined}
                                className="flex flex-col items-center justify-center gap-0.5 w-full h-full min-h-[44px] relative rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500/60"
                            >
                                {/* Active pill indicator */}
                                <div className="relative flex items-center justify-center">
                                    <div
                                        className={cn(
                                            "absolute inset-0 rounded-full transition duration-300 ease-out",
                                            isActive
                                                ? "bg-persimmon-100 scale-x-100 opacity-100 -inset-x-3 -inset-y-0.5"
                                                : "bg-transparent scale-x-0 opacity-0 -inset-x-2 -inset-y-0.5"
                                        )}
                                    />
                                    <tab.icon
                                        size={22}
                                        strokeWidth={isActive ? 2.5 : 1.8}
                                        className={cn(
                                            "relative z-10 transition duration-300",
                                            isActive
                                                ? "text-persimmon-600 scale-110"
                                                : "text-stone-400"
                                        )}
                                    />
                                </div>
                                {/* Label — shown on active, dimmed on inactive */}
                                <span
                                    className={cn(
                                        "text-[11px] font-semibold tracking-tight transition duration-300",
                                        isActive
                                            ? "text-persimmon-600 opacity-100 translate-y-0"
                                            : "text-stone-400 opacity-70 translate-y-0"
                                    )}
                                >
                                    {tab.label}
                                </span>
                            </button>
                        )
                    })}
                </div>
            </div>
        </nav>
    )
}
