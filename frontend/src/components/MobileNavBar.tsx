import { useState } from 'react'
import { Home, Package, BarChart3, Plus, Camera, MoreHorizontal, X, Search, Eye, LayoutTemplate, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCommanderStore } from '@/store/useCommanderStore'

const primaryTabs = [
    { id: 'dashboard', label: 'Home', icon: Home },
    { id: 'create', label: 'Create', icon: Plus },
    { id: 'batch-scan', label: 'Scan', icon: Camera },
    { id: 'inventory', label: 'Listings', icon: Package },
]

const moreTabs = [
    { id: 'photo-editor', label: 'Photos', icon: Camera },
    { id: 'price-research', label: 'Research', icon: Search },
    { id: 'preview', label: 'Preview', icon: Eye },
    { id: 'templates', label: 'Templates', icon: LayoutTemplate },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Settings },
]

export function MobileNavBar() {
    const activeTab = useCommanderStore(state => state.activeTab)
    const onTabChange = useCommanderStore(state => state.setActiveTab)
    const [isMenuOpen, setIsMenuOpen] = useState(false)

    const handleMoreTabClick = (tabId: string) => {
        onTabChange(tabId)
        setIsMenuOpen(false)
    }

    return (
        <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-stone-200 md:hidden z-50 transition-all duration-300">
            {/* Primary Navigation */}
            <div className="flex items-center justify-around h-16 pb-safe px-4">
                {primaryTabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => onTabChange(tab.id)}
                        className={cn(
                            "flex flex-col items-center justify-center gap-1 w-full h-full transition-colors duration-200",
                            activeTab === tab.id ? "text-sage-600" : "text-stone-400"
                        )}
                    >
                        <tab.icon size={22} strokeWidth={activeTab === tab.id ? 2.5 : 2} />
                        <span className="text-[10px] font-bold uppercase tracking-tight">{tab.label}</span>
                    </button>
                ))}

                <button
                    onClick={() => setIsMenuOpen(true)}
                    aria-label="More Options"
                    className={cn(
                        "flex flex-col items-center justify-center gap-1 w-full h-full transition-colors duration-200",
                        isMenuOpen ? "text-sage-600" : "text-stone-400"
                    )}
                >
                    <MoreHorizontal size={22} />
                    <span className="text-[10px] font-bold uppercase tracking-tight">More</span>
                </button>
            </div>

            {/* Expansible 'More' Menu Overlay */}
            <div className={cn(
                "fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 transition-opacity duration-300",
                isMenuOpen ? "opacity-100" : "opacity-0 pointer-events-none"
            )} onClick={() => setIsMenuOpen(false)}>
                <div
                    className={cn(
                        "absolute bottom-0 left-0 right-0 bg-white rounded-t-3xl p-6 transition-transform duration-300 transform",
                        isMenuOpen ? "translate-y-0" : "translate-y-full"
                    )}
                    onClick={(e) => e.stopPropagation()}
                >
                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-lg font-display font-bold text-stone-800">More Tools</h2>
                        <button
                            onClick={() => setIsMenuOpen(false)}
                            aria-label="Close menu"
                            className="p-2 bg-stone-100 rounded-full text-stone-500"
                        >
                            <X size={20} />
                        </button>
                    </div>

                    <div className="grid grid-cols-3 gap-y-6 gap-x-4 mb-8">
                        {moreTabs.map((tab) => (
                            <button
                                key={tab.id}
                                onClick={() => handleMoreTabClick(tab.id)}
                                className={cn(
                                    "flex flex-col items-center gap-2 p-3 rounded-2xl transition-all duration-200",
                                    activeTab === tab.id ? "bg-sage-50 text-sage-600 shadow-sm ring-1 ring-sage-100" : "text-stone-500 active:bg-stone-50"
                                )}
                            >
                                <div className={cn(
                                    "w-10 h-10 rounded-xl flex items-center justify-center",
                                    activeTab === tab.id ? "bg-white" : "bg-stone-50"
                                )}>
                                    <tab.icon size={20} />
                                </div>
                                <span className="text-[11px] font-bold text-center leading-tight">{tab.label}</span>
                            </button>
                        ))}
                    </div>

                    <div className="pb-safe" />
                </div>
            </div>
        </nav>
    )
}
