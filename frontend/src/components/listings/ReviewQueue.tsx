import { useEffect, useState } from 'react'
import { CheckCircle, AlertCircle, Edit3, Trash2, CheckSquare, Square, RefreshCcw, ShieldCheck, ShieldAlert, Save, X } from 'lucide-react'
import { useCommanderStore } from '@/store/useCommanderStore'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export function ReviewQueue() {
    const pendingListings = useCommanderStore(state => state.pendingListings)
    const fetchPending = useCommanderStore(state => state.fetchPending)
    const approvePending = useCommanderStore(state => state.approvePending)
    const updatePending = useCommanderStore(state => state.updatePending)
    const deletePending = useCommanderStore(state => state.deletePending)

    const [selectedIds, setSelectedIds] = useState<string[]>([])
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [isLoading, setIsLoading] = useState(true)
    const [editingId, setEditingId] = useState<string | null>(null)
    const [editValues, setEditValues] = useState<{ title: string; price: string }>({ title: '', price: '' })

    useEffect(() => {
        fetchPending().finally(() => setIsLoading(false))
    }, [fetchPending])

    const handleRefresh = async () => {
        setIsRefreshing(true)
        await fetchPending()
        setSelectedIds([]) // Clear stale selections
        setIsRefreshing(false)
    }

    const toggleSelect = (id: string) => {
        setSelectedIds(prev =>
            prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
        )
    }

    const toggleSelectAll = () => {
        if (selectedIds.length === pendingListings.length) {
            setSelectedIds([])
        } else {
            setSelectedIds(pendingListings.map(l => l.id))
        }
    }

    const handleBatchApprove = async () => {
        if (selectedIds.length === 0) return
        await approvePending(selectedIds)
        setSelectedIds([])
    }

    const handleEdit = (listing: { id: string; name: string; price: string | null }) => {
        setEditingId(listing.id)
        setEditValues({
            title: listing.name || '',
            price: listing.price || '',
        })
    }

    const handleSaveEdit = async () => {
        if (!editingId) return
        const updates: { title?: string; price?: string } = {}
        if (editValues.title) updates.title = editValues.title
        if (editValues.price) updates.price = editValues.price
        await updatePending(editingId, updates)
        setEditingId(null)
    }

    const handleCancelEdit = () => {
        setEditingId(null)
    }

    const handleDelete = async (id: string) => {
        if (window.confirm('Delete this listing and its source folder?')) {
            await deletePending(id, true)
            setSelectedIds(prev => prev.filter(i => i !== id))
        }
    }

    const getConfidenceColor = (score: number) => {
        if (score >= 0.85) return 'text-green-600 bg-green-50 border-green-200'
        if (score >= 0.70) return 'text-amber-600 bg-amber-50 border-amber-200'
        return 'text-red-600 bg-red-50 border-red-200'
    }

    if (isLoading) {
        return (
            <div className="p-6 space-y-6 animate-in fade-in duration-500">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-display font-bold text-stone-900 tracking-tight">Review Queue</h1>
                        <p className="text-stone-500 text-sm">Review and approve listings that didn't meet the auto-publish threshold.</p>
                    </div>
                </div>
                <div className="space-y-3">
                    {[1, 2, 3].map(i => (
                        <Card key={i} className="border-stone-200">
                            <CardContent className="p-0">
                                <div className="flex items-center gap-4 px-4 py-4">
                                    <div className="w-5 h-5 rounded bg-stone-200 animate-pulse" />
                                    <div className="w-12 h-12 rounded-lg bg-stone-200 animate-pulse" />
                                    <div className="flex-1 space-y-2">
                                        <div className="h-4 bg-stone-200 rounded animate-pulse w-3/4" />
                                        <div className="h-3 bg-stone-100 rounded animate-pulse w-1/2" />
                                    </div>
                                    <div className="h-6 w-16 bg-stone-200 rounded animate-pulse" />
                                    <div className="h-6 w-12 bg-stone-200 rounded-full animate-pulse" />
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        )
    }

    return (
        <div className="p-6 space-y-6 animate-in fade-in duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-display font-bold text-stone-900 tracking-tight">Review Queue</h1>
                    <p className="text-stone-500 text-sm">Review and approve listings that didn't meet the auto-publish threshold.</p>
                </div>
                <div className="flex items-center gap-3">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleRefresh}
                        aria-label="Refresh review queue"
                        className={cn("gap-2", isRefreshing && "animate-pulse")}
                    >
                        <RefreshCcw size={16} className={cn(isRefreshing && "animate-spin")} />
                        Refresh
                    </Button>
                    <Button
                        size="sm"
                        disabled={selectedIds.length === 0}
                        onClick={handleBatchApprove}
                        className="bg-sage-600 hover:bg-sage-700 gap-2 shadow-sm"
                    >
                        <CheckCircle size={16} />
                        Approve Selected ({selectedIds.length})
                    </Button>
                </div>
            </div>

            {pendingListings.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-24 bg-stone-50 rounded-3xl border-2 border-dashed border-stone-200">
                    <div className="w-16 h-16 bg-white rounded-2xl flex items-center justify-center shadow-sm mb-4 border border-stone-100">
                        <ShieldCheck className="text-stone-300" size={32} />
                    </div>
                    <h3 className="text-stone-800 font-bold text-lg">Queue Clear</h3>
                    <p className="text-stone-500 max-w-sm text-center">All listings have either been published or are waiting in the main queue.</p>
                </div>
            ) : (
                <div className="space-y-4">
                    <div className="flex items-center gap-3 px-4 py-2 text-xs font-bold text-stone-400 uppercase tracking-wider">
                        <button onClick={toggleSelectAll} aria-label={selectedIds.length === pendingListings.length ? 'Deselect all' : 'Select all'} className="hover:text-stone-600 transition-colors">
                            {selectedIds.length === pendingListings.length ? <CheckSquare size={18} className="text-persimmon-600" /> : <Square size={18} />}
                        </button>
                        <div className="flex-1 grid grid-cols-12 gap-4">
                            <span className="col-span-1">Item</span>
                            <span className="col-span-5">Title & Status</span>
                            <span className="col-span-2">Price</span>
                            <span className="col-span-2 text-center">AI Confidence</span>
                            <span className="col-span-2 text-right">Actions</span>
                        </div>
                    </div>

                    <div className="space-y-3">
                        {pendingListings.map(listing => (
                            <Card key={listing.id} className={cn(
                                "border-stone-200 overflow-hidden transition-all duration-200 hover:border-persimmon-300 hover:shadow-md",
                                selectedIds.includes(listing.id) && "ring-2 ring-persimmon-500 border-transparent shadow-lg bg-persimmon-50/30"
                            )}>
                                <CardContent className="p-0">
                                    <div className="flex items-stretch">
                                        <div
                                            className="px-4 flex items-center cursor-pointer hover:bg-stone-50 transition-colors"
                                            onClick={() => toggleSelect(listing.id)}
                                            role="checkbox"
                                            aria-checked={selectedIds.includes(listing.id) ? 'true' : 'false'}
                                            aria-label={selectedIds.includes(listing.id) ? 'Deselect listing' : 'Select listing'}
                                        >
                                            {selectedIds.includes(listing.id) ?
                                                <CheckSquare size={20} className="text-persimmon-600" /> :
                                                <Square size={20} className="text-stone-300" />
                                            }
                                        </div>

                                        <div className="flex-1 grid grid-cols-12 gap-4 py-4 pr-6 items-center">
                                            {/* Thumbnail */}
                                            <div className="col-span-1">
                                                <div className="w-12 h-12 rounded-lg bg-stone-100 border border-stone-200 overflow-hidden flex items-center justify-center">
                                                    {listing.thumbnail_url ? (
                                                        <img src={listing.thumbnail_url} className="w-full h-full object-cover" alt="" />
                                                    ) : (
                                                        <AlertCircle size={20} className="text-stone-300" />
                                                    )}
                                                </div>
                                            </div>

                                            {/* Title — inline edit or display */}
                                            <div className="col-span-5">
                                                {editingId === listing.id ? (
                                                    <input
                                                        type="text"
                                                        className="w-full px-2 py-1 text-sm font-bold text-stone-900 border border-persimmon-300 rounded-md focus:outline-none focus:ring-2 focus:ring-persimmon-500"
                                                        value={editValues.title}
                                                        onChange={e => setEditValues(prev => ({ ...prev, title: e.target.value }))}
                                                        autoFocus
                                                    />
                                                ) : (
                                                    <>
                                                        <h4 className="font-bold text-stone-900 leading-tight mb-1 truncate">{listing.display_name || listing.name}</h4>
                                                        <div className="flex items-center gap-2">
                                                            <Badge variant="outline" className="text-[10px] uppercase tracking-wider font-bold bg-amber-50 text-amber-600 border-amber-200">Pending Review</Badge>
                                                            <span className="text-[10px] text-stone-400 font-medium truncate opacity-60">{listing.folder_path}</span>
                                                        </div>
                                                    </>
                                                )}
                                            </div>

                                            {/* Price — inline edit or display */}
                                            <div className="col-span-2">
                                                {editingId === listing.id ? (
                                                    <input
                                                        type="text"
                                                        className="w-24 px-2 py-1 text-sm font-bold text-stone-900 border border-persimmon-300 rounded-md focus:outline-none focus:ring-2 focus:ring-persimmon-500"
                                                        value={editValues.price}
                                                        onChange={e => setEditValues(prev => ({ ...prev, price: e.target.value }))}
                                                        placeholder="0.00"
                                                    />
                                                ) : (
                                                    <span className="font-display font-bold text-lg text-stone-900">${listing.price || '0.00'}</span>
                                                )}
                                            </div>

                                            {/* AI Confidence */}
                                            <div className="col-span-2 flex flex-col items-center">
                                                <div className={cn(
                                                    "px-3 py-1 rounded-full border text-xs font-bold flex items-center gap-1.5 shadow-sm",
                                                    getConfidenceColor(listing.confidence_score || 0)
                                                )}>
                                                    {(listing.confidence_score || 0) < 0.85 ? <ShieldAlert size={14} /> : <ShieldCheck size={14} />}
                                                    {Math.round((listing.confidence_score || 0) * 100)}%
                                                </div>
                                            </div>

                                            {/* Actions */}
                                            <div className="col-span-2 flex items-center justify-end gap-2">
                                                {editingId === listing.id ? (
                                                    <>
                                                        <Button variant="ghost" size="icon" className="h-9 w-9 text-persimmon-600 hover:text-persimmon-800 hover:bg-persimmon-50" onClick={handleSaveEdit} aria-label="Save changes">
                                                            <Save size={18} />
                                                        </Button>
                                                        <Button variant="ghost" size="icon" className="h-9 w-9 text-stone-400 hover:text-stone-900 hover:bg-stone-100" onClick={handleCancelEdit} aria-label="Cancel editing">
                                                            <X size={18} />
                                                        </Button>
                                                    </>
                                                ) : (
                                                    <>
                                                        <Button variant="ghost" size="icon" className="h-9 w-9 text-stone-400 hover:text-stone-900 hover:bg-stone-100" onClick={() => handleEdit(listing)} aria-label="Edit listing">
                                                            <Edit3 size={18} />
                                                        </Button>
                                                        <Button variant="ghost" size="icon" className="h-9 w-9 text-stone-400 hover:text-red-600 hover:bg-red-50" onClick={() => handleDelete(listing.id)} aria-label="Remove listing">
                                                            <Trash2 size={18} />
                                                        </Button>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
