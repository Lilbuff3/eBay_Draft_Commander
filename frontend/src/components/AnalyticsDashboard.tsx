
import { useState, useEffect, useCallback } from 'react'
import {
    XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area
} from 'recharts'
import { TrendingUp, DollarSign, Package, ShoppingBag, Activity } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { fetchAnalyticsSummary, fetchRecentOrders } from '@/lib/api'
import type { SalesStats, Order } from '@/lib/api'

interface StatCardProps {
    title: string
    value: string | number
    icon: React.ElementType
    subtext: string
    bgColor: string
    iconColor: string
}

function StatCard({ title, value, icon: Icon, subtext, bgColor, iconColor }: StatCardProps) {
    return (
        <Card>
            <CardContent className="p-6">
                <div className="flex items-center justify-between space-y-0 pb-2">
                    <p className="text-sm font-medium text-muted-foreground">{title}</p>
                    <div className={`p-2 rounded-lg ${bgColor} bg-opacity-10`}>
                        <Icon className={`h-4 w-4 ${iconColor}`} />
                    </div>
                </div>
                <div className="flex flex-col gap-1">
                    <div className="text-2xl font-bold">{value}</div>
                    <p className="text-xs text-muted-foreground">{subtext}</p>
                </div>
            </CardContent>
        </Card>
    )
}

export function AnalyticsDashboard() {
    const [stats, setStats] = useState<SalesStats | null>(null)
    const [recentOrders, setRecentOrders] = useState<Order[]>([])
    const [timeRange, setTimeRange] = useState('30')
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchData = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            const [statsData, ordersData] = await Promise.all([
                fetchAnalyticsSummary(timeRange),
                fetchRecentOrders(timeRange),
            ])
            setStats(statsData)
            setRecentOrders(ordersData.orders || [])
        } catch (err) {
            const error = err as Error
            console.error("Failed to fetch analytics:", error)
            setError(error.message || "Failed to load analytics data")
        } finally {
            setIsLoading(false)
        }
    }, [timeRange])

    useEffect(() => {
        fetchData()
    }, [fetchData])

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString()
    }

    // StatCard is now defined at file scope above

    return (
        <div className="flex flex-col h-full bg-stone-50 overflow-hidden">
            {/* Header */}
            <div className="border-b bg-white px-8 py-4 flex items-center justify-between shrink-0">
                <div>
                    <h1 className="text-2xl font-display font-bold text-stone-900">Analytics</h1>
                    <p className="text-stone-500">Track your sales performance and revenue</p>
                </div>
                <div className="flex items-center gap-2">
                    <Tabs value={timeRange} onValueChange={setTimeRange}>
                        <TabsList>
                            <TabsTrigger value="7">7 Days</TabsTrigger>
                            <TabsTrigger value="30">30 Days</TabsTrigger>
                            <TabsTrigger value="90">90 Days</TabsTrigger>
                        </TabsList>
                    </Tabs>
                    <Button variant="outline" size="icon" onClick={fetchData} disabled={isLoading} aria-label="Refresh dashboard">
                        <Activity className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                    </Button>
                </div>
            </div>

            <ScrollArea className="flex-1 p-8">
                <div className="max-w-6xl mx-auto space-y-8">
                    {error && (
                        <div className="p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50 border border-red-200 flex items-center gap-2">
                            <Activity className="h-4 w-4" />
                            <span><strong>Error:</strong> {error}. Please check your eBay connection.</span>
                        </div>
                    )}

                    {/* Stats Grid */}
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
                        <StatCard
                            title="Total Revenue"
                            value={stats ? `$${stats.total_revenue.toFixed(2)}` : '$0.00'}
                            icon={DollarSign}
                            subtext="Gross sales including shipping"
                            bgColor="bg-emerald-500"
                            iconColor="text-emerald-600"
                        />
                        <StatCard
                            title="Orders"
                            value={stats ? stats.orders_count : 0}
                            icon={ShoppingBag}
                            subtext="Total completed orders"
                            bgColor="bg-blue-500"
                            iconColor="text-blue-600"
                        />
                        <StatCard
                            title="Items Sold"
                            value={stats ? stats.items_sold : 0}
                            icon={Package}
                            subtext="Total units moved"
                            bgColor="bg-purple-500"
                            iconColor="text-purple-600"
                        />
                        <StatCard
                            title="Avg Order Value"
                            value={stats ? `$${stats.average_order_value.toFixed(2)}` : '$0.00'}
                            icon={TrendingUp}
                            subtext="Revenue per order"
                            bgColor="bg-orange-500"
                            iconColor="text-orange-600"
                        />
                        <StatCard
                            title="Sell-through Rate"
                            value={stats ? `${stats.sell_through_rate || 0}%` : '0%'}
                            icon={Activity}
                            subtext={`${stats?.items_sold || 0} sold / ${(stats?.items_sold || 0) + (stats?.active_listings_count || 0)} total`}
                            bgColor="bg-pink-500"
                            iconColor="text-pink-600"
                        />
                    </div>

                    <div className="grid gap-4 md:grid-cols-3">
                        {/* Revenue Chart */}
                        <Card className="col-span-2">
                            <CardHeader>
                                <CardTitle>Revenue Trend</CardTitle>
                                <CardDescription>Daily sales performance breakdown</CardDescription>
                            </CardHeader>
                            <CardContent className="pl-2">
                                <div className="h-[350px] w-full">
                                    {stats?.chart_data && (
                                        <ResponsiveContainer width="100%" height="100%">
                                            <AreaChart data={stats.chart_data}>
                                                <defs>
                                                    <linearGradient id="colorSales" x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.1} />
                                                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                                    </linearGradient>
                                                </defs>
                                                <XAxis
                                                    dataKey="date"
                                                    stroke="#888888"
                                                    fontSize={12}
                                                    tickLine={false}
                                                    axisLine={false}
                                                    tickFormatter={(str) => {
                                                        const date = new Date(str);
                                                        return `${date.getMonth() + 1}/${date.getDate()}`;
                                                    }}
                                                />
                                                <YAxis
                                                    stroke="#888888"
                                                    fontSize={12}
                                                    tickLine={false}
                                                    axisLine={false}
                                                    tickFormatter={(value) => `$${value}`}
                                                />
                                                <Tooltip
                                                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                                    formatter={(value: number | string) => [`$${Number(value || 0).toFixed(2)}`, 'Revenue']}
                                                />
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                                                <Area
                                                    type="monotone"
                                                    dataKey="sales"
                                                    stroke="#10b981"
                                                    strokeWidth={2}
                                                    fillOpacity={1}
                                                    fill="url(#colorSales)"
                                                />
                                            </AreaChart>
                                        </ResponsiveContainer>
                                    )}
                                    {!stats?.chart_data && !isLoading && (
                                        <div className="h-full flex items-center justify-center text-stone-400">
                                            No sales data for this period
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>

                        {/* Best Sellers */}
                        <Card className="col-span-1">
                            <CardHeader>
                                <CardTitle>Best Sellers</CardTitle>
                                <CardDescription>Top performing items</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-6">
                                    {stats?.best_sellers && stats.best_sellers.length > 0 ? (
                                        stats.best_sellers.map((item, i) => (
                                            <div key={i} className="flex items-center">
                                                <div className="flex-1 space-y-1 overflow-hidden">
                                                    <p className="text-sm font-medium leading-none truncate" title={item.title}>
                                                        {item.title}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground">
                                                        {item.qty} sold
                                                    </p>
                                                </div>
                                                <div className="font-bold whitespace-nowrap ml-2">
                                                    ${item.revenue.toFixed(2)}
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-center py-6 text-stone-400">
                                            No data available
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Recent Orders Table */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Recent Orders</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4">
                                {recentOrders.length > 0 ? (
                                    recentOrders.map((order) => (
                                        <div key={order.orderId} className="flex items-center justify-between border-b border-stone-100 pb-4 last:border-0 last:pb-0">
                                            <div className="flex items-center gap-4">
                                                <div className="h-9 w-9 rounded-full bg-stone-100 flex items-center justify-center text-stone-500">
                                                    <Package size={16} />
                                                </div>
                                                <div>
                                                    <p className="text-sm font-medium text-stone-900">{order.buyer || 'Guest'}</p>
                                                    <p className="text-xs text-stone-500">
                                                        {formatDate(order.creationDate)} • {order.itemCount} item(s)
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <p className="text-sm font-bold text-stone-900">${order.total.toFixed(2)}</p>
                                                <Badge variant="secondary" className="text-[10px] mt-1">
                                                    {order.status}
                                                </Badge>
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-center py-8 text-stone-400">
                                        No recent orders found
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>

                </div>
            </ScrollArea>
        </div>
    )
}
