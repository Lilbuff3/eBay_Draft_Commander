import { useState } from 'react'
import { motion } from 'framer-motion'
import {
    TrendingUp, DollarSign, BarChart3,
    Search, ExternalLink, RefreshCw, X, Package,
    ArrowUpRight, ArrowDownRight, Minus
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

interface PriceResearchProps {
    jobId?: string
    initialQuery?: string
    onClose: () => void
}

interface SoldItem {
    title: string
    price: number
    soldDate: string
    shipping: number
    condition: string
    imageUrl?: string
}

interface PriceStats {
    average: number
    median: number
    low: number
    high: number
    sold: number
    trend: 'up' | 'down' | 'stable'
    trendPercent: number
}

// Mock data - replace with API calls
// const mockStats: PriceStats = {
//     average: 34.99,
//     median: 32.50,
//     low: 19.99,
//     high: 89.99,
//     sold: 47,
//     trend: 'up',
//     trendPercent: 12.5
// }

// const mockSoldItems: SoldItem[] = [
//     { title: 'Vintage Industrial Sensor XR-2000', price: 45.99, soldDate: '2 days ago', shipping: 8.50, condition: 'Used' },
//     { title: 'XR-2000 Sensor Module OEM', price: 39.00, soldDate: '3 days ago', shipping: 0, condition: 'Like New' },
//     { title: 'Industrial XR Sensor 2000 Series', price: 28.50, soldDate: '4 days ago', shipping: 5.99, condition: 'Used' },
//     { title: 'XR2000 Control Sensor Unit', price: 52.00, soldDate: '5 days ago', shipping: 12.00, condition: 'New' },
//     { title: 'Sensor Assembly XR-2000 Parts', price: 22.99, soldDate: '1 week ago', shipping: 4.50, condition: 'For Parts' },
// ]

export function PriceResearch({ jobId: _jobId, initialQuery = '', onClose }: PriceResearchProps) {
    const [query, setQuery] = useState(initialQuery)
    const [isLoading, setIsLoading] = useState(false)
    const [stats, setStats] = useState<PriceStats | null>(null)
    const [soldItems, setSoldItems] = useState<SoldItem[]>([])
    const [selectedTimeframe, setSelectedTimeframe] = useState<'7d' | '30d' | '90d'>('30d')

    const handleSearch = async () => {
        if (!query.trim()) return

        setIsLoading(true)
        try {
            const res = await fetch(`/api/tools/research?q=${encodeURIComponent(query)}`)
            const data = await res.json()
            setStats(data.stats)
            setSoldItems(data.items)
        } catch (error) {
            console.error('Failed to fetching prices:', error)
        } finally {
            setIsLoading(false)
        }
    }

    const TrendIcon = stats?.trend === 'up' ? ArrowUpRight : stats?.trend === 'down' ? ArrowDownRight : Minus
    const trendColor = stats?.trend === 'up' ? 'text-emerald-500' : stats?.trend === 'down' ? 'text-red-500' : 'text-stone-400'

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="bg-white rounded-3xl border border-stone-200 shadow-xl overflow-hidden"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-stone-100 bg-gradient-to-r from-emerald-50 to-white">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500 flex items-center justify-center text-white shadow-sm">
                        <BarChart3 size={20} />
                    </div>
                    <div>
                        <h2 className="font-semibold text-stone-800">Price Research</h2>
                        <p className="text-xs text-stone-400">Analyze eBay sold listings</p>
                    </div>
                </div>
                <Button variant="ghost" size="icon" onClick={onClose}>
                    <X size={18} />
                </Button>
            </div>

            <div className="p-6">
                {/* Search Bar */}
                <div className="flex gap-2 mb-6">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" size={18} />
                        <Input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                            placeholder="Search eBay sold listings..."
                            className="pl-10"
                        />
                    </div>
                    <Button onClick={handleSearch} disabled={isLoading} className="bg-emerald-500 hover:bg-emerald-600">
                        {isLoading ? (
                            <RefreshCw size={16} className="animate-spin" />
                        ) : (
                            <>Search</>
                        )}
                    </Button>
                </div>

                {/* Stats Grid */}
                {stats && (
                    <div className="grid grid-cols-4 gap-4 mb-6">
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: 0.1 }}
                            className="bg-gradient-to-br from-emerald-50 to-emerald-100/50 rounded-2xl p-4 border border-emerald-100"
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-medium text-emerald-600 uppercase tracking-wider">Average</span>
                                <DollarSign size={16} className="text-emerald-500" />
                            </div>
                            <div className="text-2xl font-bold text-stone-800">${stats.average.toFixed(2)}</div>
                            <div className={cn("flex items-center gap-1 text-xs mt-1", trendColor)}>
                                <TrendIcon size={12} />
                                {stats.trendPercent}% vs last month
                            </div>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: 0.15 }}
                            className="bg-stone-50 rounded-2xl p-4 border border-stone-100"
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-medium text-stone-500 uppercase tracking-wider">Median</span>
                                <BarChart3 size={16} className="text-stone-400" />
                            </div>
                            <div className="text-2xl font-bold text-stone-800">${stats.median.toFixed(2)}</div>
                            <div className="text-xs text-stone-400 mt-1">Middle price point</div>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: 0.2 }}
                            className="bg-stone-50 rounded-2xl p-4 border border-stone-100"
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-medium text-stone-500 uppercase tracking-wider">Range</span>
                                <TrendingUp size={16} className="text-stone-400" />
                            </div>
                            <div className="text-2xl font-bold text-stone-800">
                                ${stats.low.toFixed(0)} - ${stats.high.toFixed(0)}
                            </div>
                            <div className="text-xs text-stone-400 mt-1">Low to high</div>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: 0.25 }}
                            className="bg-stone-50 rounded-2xl p-4 border border-stone-100"
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-medium text-stone-500 uppercase tracking-wider">Sold</span>
                                <Package size={16} className="text-stone-400" />
                            </div>
                            <div className="text-2xl font-bold text-stone-800">{stats.sold}</div>
                            <div className="text-xs text-stone-400 mt-1">In last 30 days</div>
                        </motion.div>
                    </div>
                )}

                {/* Sold Items List */}
                {soldItems.length > 0 && (
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <h3 className="font-semibold text-stone-700">Recent Sales</h3>
                            <Tabs value={selectedTimeframe} onValueChange={(v) => setSelectedTimeframe(v as typeof selectedTimeframe)}>
                                <TabsList className="h-8">
                                    <TabsTrigger value="7d" className="text-xs px-2 h-6">7 Days</TabsTrigger>
                                    <TabsTrigger value="30d" className="text-xs px-2 h-6">30 Days</TabsTrigger>
                                    <TabsTrigger value="90d" className="text-xs px-2 h-6">90 Days</TabsTrigger>
                                </TabsList>
                            </Tabs>
                        </div>

                        <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
                            {soldItems.map((item, index) => (
                                <motion.div
                                    key={index}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.1 * index }}
                                    className="flex items-center justify-between p-3 bg-stone-50 rounded-xl hover:bg-stone-100 transition-colors group cursor-pointer"
                                >
                                    <div className="flex-1 min-w-0">
                                        <h4 className="text-sm font-medium text-stone-700 truncate">{item.title}</h4>
                                        <div className="flex items-center gap-2 mt-1">
                                            <Badge variant="secondary" className="text-[10px]">{item.condition}</Badge>
                                            <span className="text-xs text-stone-400">{item.soldDate}</span>
                                            {item.shipping === 0 && (
                                                <Badge className="text-[10px] bg-emerald-100 text-emerald-700">Free Ship</Badge>
                                            )}
                                        </div>
                                    </div>
                                    <div className="text-right ml-4">
                                        <div className="text-lg font-bold text-stone-800">${item.price.toFixed(2)}</div>
                                        {item.shipping > 0 && (
                                            <div className="text-xs text-stone-400">+${item.shipping.toFixed(2)} ship</div>
                                        )}
                                    </div>
                                    <ExternalLink size={14} className="ml-3 text-stone-300 group-hover:text-stone-500 transition-colors" />
                                </motion.div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Empty State */}
                {!stats && !isLoading && (
                    <div className="text-center py-12 text-stone-400">
                        <Search size={48} className="mx-auto mb-4 opacity-30" />
                        <p className="text-sm">Enter a search term to research prices</p>
                        <p className="text-xs mt-1">We'll analyze eBay sold listings for you</p>
                    </div>
                )}
            </div>
        </motion.div>
    )
}
