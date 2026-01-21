import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

interface Sale {
    orderId: string
    creationDate: string
    buyer: string
    total: number
    status: string
    itemCount: number
}

interface SalesData {
    orders: Sale[]
    total: number
    revenue: number
    period: string
}

export function SalesWidget() {
    const [data, setData] = useState<SalesData | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchSales = async () => {
        setIsLoading(true)
        setError(null)
        try {
            console.log("Fetching sales data...")
            const res = await fetch('/api/sales/recent')
            if (!res.ok) {
                console.error("Sales fetch response not ok", res.status, res.statusText)
                throw new Error(`API Error: ${res.status}`)
            }
            const json = await res.json()
            console.log("Sales data received:", json)

            if (json.error) throw new Error(json.error)
            setData(json)
        } catch (e) {
            console.error("Sales Widget Error:", e)
            setError(e instanceof Error ? e.message : 'Failed to load sales')
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        fetchSales()
    }, [])

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr)
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl border border-stone-100 shadow-sm overflow-hidden"
        >
            {/* Header */}
            <div className="px-5 py-4 border-b border-stone-100 bg-gradient-to-r from-emerald-50 to-white flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-emerald-500 flex items-center justify-center text-white">
                        <TrendingUp size={18} />
                    </div>
                    <div>
                        <h3 className="font-semibold text-stone-800">Recent Sales</h3>
                        <p className="text-xs text-stone-400">Last 30 days</p>
                    </div>
                </div>
                <Button variant="ghost" size="icon" onClick={fetchSales} disabled={isLoading}>
                    <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
                </Button>
            </div>

            {/* Stats Bar */}
            {data && (
                <div className="grid grid-cols-2 gap-px bg-stone-100">
                    <div className="bg-white p-4 text-center">
                        <div className="text-2xl font-bold text-emerald-600">${data.revenue.toFixed(2)}</div>
                        <div className="text-xs text-stone-400">Total Revenue</div>
                    </div>
                    <div className="bg-white p-4 text-center">
                        <div className="text-2xl font-bold text-stone-800">{data.total}</div>
                        <div className="text-xs text-stone-400">Orders</div>
                    </div>
                </div>
            )}

            {/* Orders List */}
            <ScrollArea className="h-48">
                {isLoading ? (
                    <div className="flex items-center justify-center h-full text-stone-400">
                        <RefreshCw size={20} className="animate-spin mr-2" />
                        Loading sales...
                    </div>
                ) : error ? (
                    <div className="flex items-center justify-center h-full text-red-500 text-sm p-4">
                        {error}
                    </div>
                ) : data?.orders.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-stone-400">
                        No recent sales
                    </div>
                ) : (
                    <div className="divide-y divide-stone-100">
                        {data?.orders.map(order => (
                            <div key={order.orderId} className="px-4 py-3 hover:bg-stone-50 transition-colors">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <div className="text-sm font-medium text-stone-800">
                                            {order.buyer}
                                        </div>
                                        <div className="text-xs text-stone-400">
                                            {formatDate(order.creationDate)} • {order.itemCount} item{order.itemCount > 1 ? 's' : ''}
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-sm font-semibold text-emerald-600">
                                            ${order.total.toFixed(2)}
                                        </div>
                                        <Badge variant="secondary" className="text-[10px] bg-emerald-50 text-emerald-700">
                                            {order.status}
                                        </Badge>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </ScrollArea>
        </motion.div>
    )
}
