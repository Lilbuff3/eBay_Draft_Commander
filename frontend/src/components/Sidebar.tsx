import { LayoutTemplate, Package, BarChart3, Settings, Camera, Search, Eye, PlusCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
// Tooltip imports removed

interface SidebarProps {
    activeTab: string
    setActiveTab: (tab: string) => void
    className?: string
}

const navGroups = [
    {
        title: "Workspace",
        items: [
            { id: 'dashboard', icon: LayoutTemplate, label: 'Queue' },
            { id: 'create', icon: PlusCircle, label: 'New Listing' },
        ]
    },
    {
        title: "Tools",
        items: [
            { id: 'batch-scan', icon: Package, label: 'Batch Scan' },
            { id: 'photo-editor', icon: Camera, label: 'Photo Editor' },
            { id: 'price-research', icon: Search, label: 'Price Research' },
            { id: 'preview', icon: Eye, label: 'Preview' },
            { id: 'templates', icon: LayoutTemplate, label: 'Templates' },
        ]
    },
    {
        title: "Business",
        items: [
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

export function Sidebar({ activeTab, setActiveTab, className }: SidebarProps) {
    return (
        <div className={cn("w-64 bg-white border-r border-stone-200 flex flex-col py-6 h-full z-20 shadow-sm transition-all duration-300", className)}>
            {/* Logo */}
            <div className="px-6 mb-8 flex items-center gap-3">
                <div className="w-8 h-8 bg-sage-600 rounded-lg flex items-center justify-center text-white font-bold font-display shadow-sm">
                    E
                </div>
                <div className="flex flex-col">
                    <span className="font-display font-bold text-xl text-stone-800 tracking-tight leading-none">Draft Commander</span>
                    <span className="text-[10px] uppercase font-bold text-stone-400 tracking-wider">v1.1.0</span>
                </div>
            </div>

            {/* Navigation */}
            <div className="flex-1 overflow-y-auto px-4 space-y-6">
                {navGroups.map((group, groupIndex) => (
                    <div key={groupIndex}>
                        <h3 className="px-2 text-xs font-bold text-stone-400 uppercase tracking-wider mb-2">{group.title}</h3>
                        <div className="space-y-1">
                            {group.items.map(item => (
                                <button
                                    key={item.id}
                                    onClick={() => setActiveTab(item.id)}
                                    className={cn(
                                        'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                                        activeTab === item.id
                                            ? 'bg-sage-50 text-sage-700 shadow-sm ring-1 ring-sage-200'
                                            : 'text-stone-500 hover:bg-stone-50 hover:text-stone-900'
                                    )}
                                >
                                    <item.icon size={18} className={cn(
                                        activeTab === item.id ? "text-sage-600" : "text-stone-400 group-hover:text-stone-500"
                                    )} />
                                    {item.label}
                                </button>
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            {/* User / Footer could go here */}
        </div>
    )
}
