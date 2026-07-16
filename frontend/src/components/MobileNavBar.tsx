import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
    LayoutTemplate, Package, BookOpen, ShoppingBag, ScanBarcode,
    Wallet, ShieldCheck, Settings as SettingsIcon, MoreHorizontal,
    type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { fetchJobs } from '@/lib/api'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useHaptics } from '@/hooks/useHaptics'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'

interface NavItem {
    id: string
    label: string
    icon: LucideIcon
    hint?: string
}

// Five slots is the ceiling on a 360px phone. Review earns one because it gates
// whether AI listings go live; Source/Books/Profit/Settings live behind More.
const PRIMARY: NavItem[] = [
    { id: 'dashboard', label: 'Home', icon: LayoutTemplate },
    { id: 'review', label: 'Review', icon: ShieldCheck },
    { id: 'inventory', label: 'Inventory', icon: Package },
    { id: 'orders', label: 'Orders', icon: ShoppingBag },
]

const SECONDARY: NavItem[] = [
    { id: 'sourcing', label: 'Source', icon: ScanBarcode, hint: 'Scan a barcode before you buy' },
    { id: 'batch-scan', label: 'Books', icon: BookOpen, hint: 'Bulk-list books by ISBN' },
    { id: 'profit', label: 'Profit', icon: Wallet, hint: 'Real net per sale' },
    { id: 'settings', label: 'Settings', icon: SettingsIcon, hint: 'eBay auth, pricing, automation' },
]

const SECONDARY_IDS = SECONDARY.map(t => t.id)

export function MobileNavBar() {
    const activeTab = useCommanderStore(state => state.activeTab)
    const onTabChange = useCommanderStore(state => state.setActiveTab)
    const { tap } = useHaptics()
    const [moreOpen, setMoreOpen] = useState(false)

    // Badge the Review tab so a held listing is visible without opening it.
    const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs })
    const reviewCount = jobs.filter(j => j.status === 'pending_review').length

    const go = (tabId: string) => {
        if (tabId !== activeTab) {
            tap()
            onTabChange(tabId)
        }
        setMoreOpen(false)
    }

    const openMore = () => {
        tap()
        setMoreOpen(true)
    }

    const renderTab = (tab: NavItem) => {
        const isActive = activeTab === tab.id
        const badge = tab.id === 'review' ? reviewCount : 0
        return (
            <button
                key={tab.id}
                onClick={() => go(tab.id)}
                aria-label={badge > 0 ? `${tab.label}, ${badge} waiting` : tab.label}
                aria-current={isActive ? 'page' : undefined}
                className="flex flex-col items-center justify-center gap-1 flex-1 min-w-0 h-full min-h-[44px] transition-transform active:scale-95 focus-visible:outline-none"
            >
                <span className="relative">
                    <tab.icon
                        size={22}
                        strokeWidth={isActive ? 2.5 : 2}
                        className={cn('transition-colors', isActive ? 'text-persimmon-600' : 'text-stone-500')}
                    />
                    {badge > 0 && (
                        <span className="absolute -top-1.5 -right-2 min-w-[16px] h-4 px-1 rounded-full bg-persimmon-600 text-white text-xs font-bold grid place-items-center">
                            {badge > 9 ? '9+' : badge}
                        </span>
                    )}
                </span>
                <span
                    className={cn(
                        'text-xs font-semibold tracking-tight transition-colors truncate max-w-full',
                        isActive ? 'text-persimmon-600' : 'text-stone-500'
                    )}
                >
                    {tab.label}
                </span>
            </button>
        )
    }

    const moreActive = SECONDARY_IDS.includes(activeTab)

    return (
        <>
            <nav className="fixed bottom-0 left-0 right-0 md:hidden z-50">
                <div className="bg-paper-card/95 backdrop-blur-2xl border-t border-stone-200 pb-safe">
                    <div className="flex items-stretch justify-around h-[64px] px-1">
                        {PRIMARY.map(renderTab)}

                        <button
                            onClick={openMore}
                            aria-label="More"
                            aria-haspopup="dialog"
                            aria-current={moreActive ? 'page' : undefined}
                            className="flex flex-col items-center justify-center gap-1 flex-1 min-w-0 h-full min-h-[44px] transition-transform active:scale-95 focus-visible:outline-none"
                        >
                            <MoreHorizontal
                                size={22}
                                strokeWidth={moreActive ? 2.5 : 2}
                                className={cn('transition-colors', moreActive ? 'text-persimmon-600' : 'text-stone-500')}
                            />
                            <span
                                className={cn(
                                    'text-xs font-semibold tracking-tight transition-colors',
                                    moreActive ? 'text-persimmon-600' : 'text-stone-500'
                                )}
                            >
                                More
                            </span>
                        </button>
                    </div>
                </div>
            </nav>

            <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
                <SheetContent side="bottom" className="rounded-t-3xl pb-safe md:hidden">
                    <SheetHeader className="pb-0">
                        <SheetTitle className="font-display text-lg">More</SheetTitle>
                        <SheetDescription className="sr-only">Sourcing, books, profit and settings</SheetDescription>
                    </SheetHeader>
                    <div className="flex flex-col gap-1 px-2 pb-4">
                        {SECONDARY.map(tab => {
                            const isActive = activeTab === tab.id
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => go(tab.id)}
                                    aria-current={isActive ? 'page' : undefined}
                                    className={cn(
                                        'flex items-center gap-3.5 w-full rounded-2xl px-3 py-3 text-left transition-colors min-h-[56px]',
                                        isActive ? 'bg-persimmon-50' : 'hover:bg-stone-100'
                                    )}
                                >
                                    <span
                                        className={cn(
                                            'w-10 h-10 rounded-xl grid place-items-center shrink-0',
                                            isActive ? 'bg-persimmon-600 text-white' : 'bg-stone-100 text-stone-600'
                                        )}
                                    >
                                        <tab.icon size={19} strokeWidth={2.25} />
                                    </span>
                                    <span className="min-w-0">
                                        <span className={cn('block text-[15px] font-semibold', isActive ? 'text-persimmon-700' : 'text-ink-800')}>
                                            {tab.label}
                                        </span>
                                        {tab.hint && <span className="block text-xs text-stone-500 truncate">{tab.hint}</span>}
                                    </span>
                                </button>
                            )
                        })}
                    </div>
                </SheetContent>
            </Sheet>
        </>
    )
}
