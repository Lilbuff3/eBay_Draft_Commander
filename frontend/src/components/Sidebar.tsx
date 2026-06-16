import { LayoutTemplate, Package, BarChart3, Settings, Layers } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCommanderStore } from '@/store/useCommanderStore'

interface SidebarProps {
    className?: string
}

const navGroups = [
    {
        title: "Workspace",
        items: [
            { id: 'dashboard', icon: LayoutTemplate, label: 'Dashboard' },
            { id: 'inventory', icon: Package, label: 'Inventory' },
            { id: 'analytics', icon: BarChart3, label: 'Analytics' },
        ]
    },
    {
        title: "System",
        items: [
            { id: 'settings', icon: Settings, label: 'Settings' },
        ]
    }
]

export function Sidebar({ className }: SidebarProps) {
    const activeTab = useCommanderStore(state => state.activeTab)
    const setActiveTab = useCommanderStore(state => state.setActiveTab)
    const ebayStatus = useCommanderStore(state => state.ebayStatus)
    const connected = ebayStatus === 'connected'

    return (
        <div className={cn("w-64 bg-ink-800 flex flex-col py-6 h-full z-20 transition duration-300", className)}>
            {/* Logo */}
            <div className="px-5 mb-9 flex items-center gap-3">
                <div className="w-9 h-9 bg-persimmon-500 rounded-xl flex items-center justify-center text-white shadow-sm">
                    <Layers size={19} strokeWidth={2.25} />
                </div>
                <div className="flex flex-col">
                    <span className="font-display font-bold text-lg text-paper tracking-tight leading-none">Draft Commander</span>
                    <span className="text-[10px] uppercase font-semibold text-ink-400 tracking-[0.12em] mt-0.5">v1.1.0</span>
                </div>
            </div>

            {/* Navigation */}
            <div className="flex-1 overflow-y-auto px-3 space-y-6">
                {navGroups.map((group, groupIndex) => (
                    <div key={groupIndex}>
                        <h3 className="px-3 text-[10px] font-semibold text-ink-400 uppercase tracking-[0.14em] mb-2">{group.title}</h3>
                        <div className="space-y-1">
                            {group.items.map(item => {
                                const isActive = activeTab === item.id
                                return (
                                    <button
                                        key={item.id}
                                        onClick={() => setActiveTab(item.id)}
                                        className={cn(
                                            'group relative w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition duration-200',
                                            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-persimmon-500/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-800',
                                            isActive
                                                ? 'bg-ink-600 text-paper'
                                                : 'text-stone-400 hover:bg-ink-700 hover:text-stone-200'
                                        )}
                                    >
                                        {/* Active accent bar */}
                                        <span className={cn(
                                            'absolute left-0 top-1/2 -translate-y-1/2 w-1 rounded-r-full bg-persimmon-500 transition duration-200',
                                            isActive ? 'h-5 opacity-100' : 'h-0 opacity-0'
                                        )} />
                                        <item.icon size={18} className={cn(
                                            'transition-colors',
                                            isActive ? 'text-persimmon-400' : 'text-stone-500 group-hover:text-stone-300'
                                        )} />
                                        {item.label}
                                    </button>
                                )
                            })}
                        </div>
                    </div>
                ))}
            </div>

            {/* eBay connection status */}
            <div className="px-3 mt-4">
                <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-ink-700/70 text-xs font-medium">
                    <span className="relative flex h-2 w-2">
                        {connected && <span className="absolute inline-flex h-full w-full rounded-full bg-sage-400 opacity-60 animate-ping" />}
                        <span className={cn('relative inline-flex h-2 w-2 rounded-full', connected ? 'bg-sage-400' : ebayStatus === 'checking' ? 'bg-clay-400' : 'bg-red-500')} />
                    </span>
                    <span className={connected ? 'text-sage-200' : 'text-stone-400'}>
                        {connected ? 'eBay linked' : ebayStatus === 'checking' ? 'Checking eBay…' : 'eBay offline'}
                    </span>
                </div>
            </div>
        </div>
    )
}
