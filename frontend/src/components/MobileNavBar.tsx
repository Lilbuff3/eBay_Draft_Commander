import { Home, Package, BarChart3, Plus } from 'lucide-react'
import { cn } from '@/lib/utils'

interface MobileNavBarProps {
    activeTab: string
    onTabChange: (tab: string) => void
}

export function MobileNavBar({ activeTab, onTabChange }: MobileNavBarProps) {
    const tabs = [
        { id: 'dashboard', label: 'Home', icon: Home },
        { id: 'create', label: 'Create', icon: Plus },
        { id: 'inventory', label: 'Listings', icon: Package },
        { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    ]

    return (
        <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 z-50 safe-area-inset-bottom">
            <div className="flex justify-around items-center h-16">
                {tabs.map((tab) => {
                    const Icon = tab.icon
                    const isActive = activeTab === tab.id

                    return (
                        <button
                            key={tab.id}
                            onClick={() => onTabChange(tab.id)}
                            className={cn(
                                "flex flex-col items-center justify-center gap-1 px-3 py-2",
                                "min-w-[60px] min-h-[44px]", // Touch-friendly size
                                "active:scale-95 transition-all duration-200",
                                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg",
                                isActive
                                    ? "text-blue-600 dark:text-blue-400"
                                    : "text-slate-600 dark:text-slate-400"
                            )}
                            aria-label={tab.label}
                            aria-current={isActive ? 'page' : undefined}
                        >
                            <Icon
                                size={24}
                                className={cn(
                                    "transition-transform",
                                    isActive && "scale-110"
                                )}
                            />
                            <span className={cn(
                                "text-xs font-medium transition-all",
                                isActive && "font-semibold"
                            )}>
                                {tab.label}
                            </span>
                        </button>
                    )
                })}
            </div>
        </nav>
    )
}
