import { LayoutTemplate, Package, BarChart3, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip'

interface SidebarProps {
    activeTab: string
    setActiveTab: (tab: string) => void
    className?: string
}

const navItems = [
    { id: 'dashboard', icon: LayoutTemplate, label: 'Dashboard' },
    { id: 'inventory', icon: Package, label: 'Inventory' },
    { id: 'analytics', icon: BarChart3, label: 'Analytics' },
    { id: 'settings', icon: Settings, label: 'Settings' },
]

export function Sidebar({ activeTab, setActiveTab, className }: SidebarProps) {
    return (
        <TooltipProvider delayDuration={0}>
            <div className={cn("w-20 bg-white border-r border-stone-200 flex flex-col items-center py-6 h-full z-20 shadow-sm", className)}>
                {/* Logo */}
                <div className="mb-8 p-2 bg-sage-50 rounded-xl">
                    <div className="w-8 h-8 bg-sage-600 rounded-lg flex items-center justify-center text-white font-bold font-display">
                        E
                    </div>
                </div>

                {/* Navigation */}
                <div className="flex flex-col gap-6 w-full px-2">
                    {navItems.map(item => (
                        <Tooltip key={item.id}>
                            <TooltipTrigger asChild>
                                <button
                                    onClick={() => setActiveTab(item.id)}
                                    className={cn(
                                        'w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 mx-auto',
                                        activeTab === item.id
                                            ? 'bg-sage-600 text-white shadow-lg shadow-sage-200'
                                            : 'text-stone-400 hover:bg-stone-100 hover:text-sage-600'
                                    )}
                                >
                                    <item.icon size={22} />
                                </button>
                            </TooltipTrigger>
                            <TooltipContent side="right">
                                {item.label}
                            </TooltipContent>
                        </Tooltip>
                    ))}
                </div>
            </div>
        </TooltipProvider>
    )
}
