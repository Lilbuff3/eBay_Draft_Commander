
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { X, RefreshCw, Download, CheckCircle, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'

interface LegacyItem {
    listingId: string
    title: string
    price: number
    sku: string | null
    imageUrl: string | null
    inInventory: boolean
}

interface MigrationModalProps {
    onClose: () => void
    onSuccess: () => void
}

export function MigrationModal({ onClose, onSuccess }: MigrationModalProps) {
    const [items, setItems] = useState<LegacyItem[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
    const [isMigrating, setIsMigrating] = useState(false)
    const [migrationResult, setMigrationResult] = useState<{ success: number; failed: number } | null>(null)

    const fetchLegacyItems = async () => {
        setIsLoading(true)
        setError(null)
        try {
            const res = await fetch('/api/migration/check')
            const json = await res.json()
            if (json.error) throw new Error(json.error)

            setItems(json.items || [])
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to scan legacy listings')
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        fetchLegacyItems()
    }, [])

    const toggleSelect = (id: string) => {
        const newSet = new Set(selectedIds)
        if (newSet.has(id)) newSet.delete(id)
        else newSet.add(id)
        setSelectedIds(newSet)
    }

    const toggleSelectAll = () => {
        // Only select items NOT already in inventory
        const eligible = items.filter(i => !i.inInventory)
        if (selectedIds.size === eligible.length) {
            setSelectedIds(new Set())
        } else {
            setSelectedIds(new Set(eligible.map(i => i.listingId)))
        }
    }

    const handleMigrate = async () => {
        if (selectedIds.size === 0) return

        setIsMigrating(true)
        try {
            const res = await fetch('/api/migration/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ listingIds: Array.from(selectedIds) })
            })
            const json = await res.json()

            if (json.error) throw new Error(json.error)

            // Analyze results
            const successCount = json.responses?.filter((r: any) => r.statusCode === 200).length || 0
            const failCount = (json.responses?.length || 0) - successCount

            setMigrationResult({ success: successCount, failed: failCount })

            if (successCount > 0) {
                // Refresh list to exclude migrated items
                fetchLegacyItems()
                setSelectedIds(new Set())
                onSuccess() // Trigger inventory refresh in parent
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Migration failed')
        } finally {
            setIsMigrating(false)
        }
    }

    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden flex flex-col max-h-[80vh]"
            >
                {/* Header */}
                <div className="px-6 py-4 border-b border-stone-100 bg-stone-50 flex items-center justify-between">
                    <div>
                        <h2 className="text-lg font-semibold text-stone-800">Import Legacy Listings</h2>
                        <p className="text-sm text-stone-500">Migrate website listings to Inventory Sync</p>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <X size={20} />
                    </Button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-hidden relative">
                    {/* Status Message */}
                    {migrationResult && (
                        <div className={`mx-6 mt-4 p-3 rounded-lg flex items-center gap-2 ${migrationResult.failed === 0 ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'}`}>
                            <CheckCircle size={18} />
                            <span className="text-sm font-medium">
                                Migrated {migrationResult.success} items.
                                {migrationResult.failed > 0 && ` (${migrationResult.failed} failed)`}
                            </span>
                        </div>
                    )}

                    <ScrollArea className="h-full">
                        {isLoading ? (
                            <div className="flex flex-col items-center justify-center h-64 text-stone-400 gap-3">
                                <RefreshCw size={32} className="animate-spin text-blue-500" />
                                <p>Scanning eBay account...</p>
                            </div>
                        ) : error ? (
                            <div className="flex flex-col items-center justify-center h-64 text-red-500 p-6 text-center gap-2">
                                <AlertCircle size={32} />
                                <p className="font-medium">Scan failed</p>
                                <p className="text-sm opacity-80">{error}</p>
                                <Button variant="outline" size="sm" onClick={fetchLegacyItems} className="mt-4">Retry</Button>
                            </div>
                        ) : items.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-64 text-stone-400">
                                <p>No legacy listings found.</p>
                                <p className="text-sm">Everything seems to be in sync!</p>
                            </div>
                        ) : (
                            <div className="p-6">
                                <div className="flex items-center justify-between mb-2">
                                    <div className="text-sm font-medium text-stone-500">
                                        Found {items.length} items ({items.filter(i => i.inInventory).length} already synced)
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={toggleSelectAll}
                                        className="text-blue-600 hover:text-blue-700"
                                    >
                                        Select All Eligible
                                    </Button>
                                </div>

                                <div className="border border-stone-200 rounded-lg divide-y divide-stone-100">
                                    {items.map(item => (
                                        <div key={item.listingId} className={`p-3 flex items-center gap-4 ${item.inInventory ? 'bg-stone-50 opacity-60' : 'hover:bg-blue-50/50'}`}>
                                            <input
                                                type="checkbox"
                                                checked={selectedIds.has(item.listingId)}
                                                onChange={() => toggleSelect(item.listingId)}
                                                disabled={item.inInventory}
                                                className="w-4 h-4 rounded border-stone-300 text-blue-600 focus:ring-blue-500"
                                            />

                                            <div className="w-12 h-12 rounded bg-stone-100 overflow-hidden shrink-0 border border-stone-200">
                                                {item.imageUrl && <img src={item.imageUrl} alt="" className="w-full h-full object-cover" />}
                                            </div>

                                            <div className="flex-1 min-w-0">
                                                <div className="font-medium text-stone-800 truncate" title={item.title}>
                                                    {item.title}
                                                </div>
                                                <div className="flex items-center gap-3 text-xs text-stone-500 mt-0.5">
                                                    <span>ID: {item.listingId}</span>
                                                    <span>${item.price.toFixed(2)}</span>
                                                    {item.sku && <span>SKU: {item.sku}</span>}
                                                </div>
                                            </div>

                                            {item.inInventory && (
                                                <Badge variant="outline" className="bg-stone-100 text-stone-500 border-stone-200 shrink-0">
                                                    Synced
                                                </Badge>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </ScrollArea>
                </div>

                {/* Footer */}
                <div className="px-6 py-4 border-t border-stone-100 bg-stone-50 flex justify-end gap-3">
                    <Button variant="outline" onClick={onClose} disabled={isMigrating}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleMigrate}
                        disabled={selectedIds.size === 0 || isMigrating}
                        className="bg-blue-600 hover:bg-blue-700 text-white min-w-[120px]"
                    >
                        {isMigrating ? (
                            <>
                                <RefreshCw size={16} className="animate-spin mr-2" />
                                Importing...
                            </>
                        ) : (
                            <>
                                <Download size={16} className="mr-2" />
                                Import ({selectedIds.size})
                            </>
                        )}
                    </Button>
                </div>
            </motion.div>
        </div>
    )
}
