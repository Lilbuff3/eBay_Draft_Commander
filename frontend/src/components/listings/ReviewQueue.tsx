import { useEffect, useState } from 'react'
import { CheckCircle, AlertCircle, Edit3, Trash2, CheckSquare, Square, RefreshCcw, ShieldCheck, ShieldAlert, Save, X } from 'lucide-react'
import { useCommanderStore } from '@/store/useCommanderStore'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
    Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'

export function ReviewQueue() {
    const pendingListings = useCommanderStore(state => state.pendingListings)
    const fetchPending = useCommanderStore(state => state.fetchPending)
    const approvePending = useCommanderStore(state => state.approvePending)
    const updatePending = useCommanderStore(state => state.updatePending)
    const deletePending = useCommanderStore(state => state.deletePending)

    const [selectedIds, setSelectedIds] = useState<string[]>([])
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [isLoading, setIsLoading] = useState(true)
    const [loadFailed, setLoadFailed] = useState(false)
    const [editingId, setEditingId] = useState<string | null>(null)
    const [editValues, setEditValues] = useState<{ title: string; price: string }>({ title: '', price: '' })
    const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)

    useEffect(() => {
        fetchPending().then(ok => setLoadFailed(!ok)).finally(() => setIsLoading(false))
    }, [fetchPending])

    const handleRefresh = async () => {
        setIsRefreshing(true)
        const ok = await fetchPending()
        setLoadFailed(!ok)
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
        const title = editValues.title.trim()
        const price = editValues.price.trim()
        if (title) updates.title = title
        const priceNum = parseFloat(price)
        if (price && !isNaN(priceNum) && priceNum > 0) updates.price = priceNum.toFixed(2)
        if (Object.keys(updates).length === 0) { setEditingId(null); return }
        await updatePending(editingId, updates)
        setEditingId(null)
    }

    const handleCancelEdit = () => {
        setEditingId(null)
    }

    const confirmDelete = async () => {
        if (!pendingDeleteId) return
        await deletePending(pendingDeleteId, true)
        setSelectedIds(prev => prev.filter(i => i !== pendingDeleteId))
        setPendingDeleteId(null)
    }

    const getConfidenceColor = (score: number) => {
        if (score >= 0.85) return 'text-sage-700 bg-sage-100 border-sage-200'
        if (score >= 0.70) return 'text-clay-600 bg-clay-300/25 border-clay-400/50'
        return 'text-red-700 bg-red-50 border-red-200'
    }

    if (isLoading) {
        return (
            <div className="p-4 md:p-6 space-y-6 animate-in fade-in duration-500">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-display font-bold text-ink-800 tracking-tight">Review Queue</h1>
                        <p className="text-stone-500 text-sm">Review and approve listings that didn't meet the auto-publish threshold.</p>
                    </div>
                </div>
                <div className="space-y-3">
                    {[1, 2, 3].map(i => (
                        <Card key={i} className="border-stone-200 bg-paper-card shadow-sm rounded-3xl">
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
        <div className="p-4 md:p-6 pb-24 md:pb-6 space-y-6 animate-in fade-in duration-500">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-display font-bold text-ink-800 tracking-tight">Review Queue</h1>
                    <p className="text-stone-500 text-sm">Review and approve listings that didn't meet the auto-publish threshold.</p>
                </div>
                <div className="flex items-center gap-3">
                    <Button
                        variant="outline"
                        onClick={handleRefresh}
                        aria-label="Refresh review queue"
                        className={cn('gap-2', isRefreshing && 'animate-pulse')}
                    >
                        <RefreshCcw size={16} className={cn(isRefreshing && 'animate-spin')} />
                        Refresh
                    </Button>
                    <Button
                        disabled={selectedIds.length === 0}
                        onClick={handleBatchApprove}
                        className="gap-2 flex-1 sm:flex-none disabled:opacity-50"
                    >
                        <CheckCircle size={16} />
                        Approve ({selectedIds.length})
                    </Button>
                </div>
            </div>

            {loadFailed && pendingListings.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-24 bg-paper-card border-2 border-dashed border-red-200 rounded-3xl">
                    <div className="w-16 h-16 bg-red-50 rounded-2xl flex items-center justify-center mb-4 border border-red-200">
                        <AlertCircle className="text-red-500" size={32} />
                    </div>
                    <h3 className="text-ink-800 font-bold text-lg">Couldn't load the review queue</h3>
                    <p className="text-stone-500 max-w-sm text-center mb-4">The backend didn't respond — there may still be listings waiting for review.</p>
                    <Button variant="outline" onClick={handleRefresh} className="gap-2">
                        <RefreshCcw size={16} /> Retry
                    </Button>
                </div>
            ) : pendingListings.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-24 bg-paper-card border-2 border-dashed border-stone-200 rounded-3xl">
                    <div className="w-16 h-16 bg-sage-50 rounded-2xl flex items-center justify-center mb-4 border border-sage-200">
                        <ShieldCheck className="text-sage-500" size={32} />
                    </div>
                    <h3 className="text-ink-800 font-bold text-lg">Queue Clear</h3>
                    <p className="text-stone-500 max-w-sm text-center">All listings have either been published or are waiting in the main queue.</p>
                </div>
            ) : (
                <div className="space-y-4">
                    <div className="flex items-center gap-3 px-4 py-2 text-xs font-bold text-stone-500 uppercase tracking-wider">
                        <button
                            onClick={toggleSelectAll}
                            aria-label={selectedIds.length === pendingListings.length ? 'Deselect all' : 'Select all'}
                            className="w-11 h-11 -ml-2.5 grid place-items-center rounded-lg hover:text-persimmon-600 hover:bg-stone-100 transition-colors"
                        >
                            {selectedIds.length === pendingListings.length ? <CheckSquare size={18} className="text-persimmon-600" /> : <Square size={18} />}
                        </button>
                        <div className="flex-1 hidden sm:grid grid-cols-12 gap-4">
                            <span className="col-span-1">Item</span>
                            <span className="col-span-5">Title & Status</span>
                            <span className="col-span-2">Price</span>
                            <span className="col-span-2 text-center">ID Confidence</span>
                            <span className="col-span-2 text-right">Actions</span>
                        </div>
                        <span className="flex-1 sm:hidden">Select all</span>
                    </div>

                    <div className="space-y-3">
                        {pendingListings.map(listing => (
                            <Card key={listing.id} className={cn(
                                'overflow-hidden bg-paper-card border-stone-200 shadow-sm transition-all duration-300 hover:border-stone-300 hover:shadow-md',
                                selectedIds.includes(listing.id) && 'ring-2 ring-persimmon-500 border-transparent'
                            )}>
                                <CardContent className="p-0">
                                    <div className="flex items-stretch">
                                        <button
                                            type="button"
                                            className="px-4 flex items-center hover:bg-stone-100 transition-colors min-w-[44px]"
                                            onClick={() => toggleSelect(listing.id)}
                                            role="checkbox"
                                            aria-checked={selectedIds.includes(listing.id) ? 'true' : 'false'}
                                            aria-label={selectedIds.includes(listing.id) ? 'Deselect listing' : 'Select listing'}
                                        >
                                            {selectedIds.includes(listing.id) ?
                                                <CheckSquare size={20} className="text-persimmon-600" /> :
                                                <Square size={20} className="text-stone-400" />
                                            }
                                        </button>

                                        <div className="flex-1 py-4 pr-4 sm:pr-6 flex flex-col gap-3 sm:grid sm:grid-cols-12 sm:gap-4 sm:items-center">
                                            {/* Thumbnail + title share a row on mobile; grid cells on sm+ */}
                                            <div className="flex items-center gap-3 min-w-0 sm:contents">
                                            {/* Thumbnail */}
                                            <div className="shrink-0 sm:col-span-1">
                                                <div className="w-12 h-12 rounded-lg bg-stone-100 border border-stone-200 overflow-hidden flex items-center justify-center">
                                                    {listing.thumbnail_url ? (
                                                        <img src={listing.thumbnail_url} className="w-full h-full object-cover" alt="" />
                                                    ) : (
                                                        <AlertCircle size={20} className="text-stone-400" />
                                                    )}
                                                </div>
                                            </div>

                                            {/* Title — inline edit or display */}
                                            <div className="min-w-0 flex-1 sm:col-span-5">
                                                {editingId === listing.id ? (
                                                    <Input
                                                        value={editValues.title}
                                                        onChange={e => setEditValues(prev => ({ ...prev, title: e.target.value }))}
                                                        autoFocus
                                                    />
                                                ) : (
                                                    <>
                                                        <h4 className="font-bold text-ink-800 leading-tight mb-1 truncate">{listing.display_name || listing.name}</h4>
                                                        <div className="flex items-center gap-2">
                                                            <Badge variant="outline" className="text-[10px] uppercase tracking-wider font-bold bg-clay-300/25 text-clay-600 border-clay-400/50">Pending Review</Badge>
                                                            <span className="text-xs text-stone-400 font-medium truncate">{listing.folder_path}</span>
                                                        </div>
                                                        {listing.error_message && (
                                                            <p className="text-xs text-clay-600 mt-1 leading-snug">
                                                                {listing.error_message}
                                                            </p>
                                                        )}
                                                    </>
                                                )}
                                            </div>
                                            </div>

                                            {/* Price — inline edit or display */}
                                            <div className="sm:col-span-2">
                                                {editingId === listing.id ? (
                                                    <Input
                                                        className="w-24"
                                                        inputMode="decimal"
                                                        value={editValues.price}
                                                        onChange={e => setEditValues(prev => ({ ...prev, price: e.target.value }))}
                                                        placeholder="0.00"
                                                    />
                                                ) : (
                                                    <div className="flex flex-col">
                                                        <span className="font-display font-bold text-lg text-persimmon-600">${listing.price || '0.00'}</span>
                                                        {listing.ai_data?.pricing_confidence && (
                                                            <span className={cn(
                                                                'text-[10px] font-semibold mt-1 px-1.5 py-0.5 rounded border w-fit capitalize',
                                                                listing.ai_data.pricing_confidence === 'high' && 'text-sage-700 bg-sage-100 border-sage-200',
                                                                listing.ai_data.pricing_confidence === 'medium' && 'text-stone-600 bg-stone-100 border-stone-200',
                                                                listing.ai_data.pricing_confidence === 'low' && 'text-clay-600 bg-clay-300/25 border-clay-400/50',
                                                                listing.ai_data.pricing_confidence === 'user' && 'text-stone-500 bg-stone-100 border-stone-200'
                                                            )}>
                                                                {listing.ai_data.pricing_confidence === 'user' ? 'Manual' : `${listing.ai_data.pricing_confidence} Price`}
                                                            </span>
                                                        )}
                                                    </div>
                                                )}
                                            </div>

                                            {/* AI Confidence */}
                                            <div className="sm:col-span-2 flex sm:flex-col items-start sm:items-center">
                                                <div className={cn(
                                                    'px-3 py-1 rounded-full border text-xs font-bold flex items-center gap-1.5',
                                                    getConfidenceColor(listing.confidence_score || 0)
                                                )}>
                                                    {(listing.confidence_score || 0) < 0.85 ? <ShieldAlert size={14} /> : <ShieldCheck size={14} />}
                                                    {Math.round((listing.confidence_score || 0) * 100)}%
                                                </div>
                                            </div>

                                            {/* Actions */}
                                            <div className="sm:col-span-2 flex items-center justify-end gap-2">
                                                {editingId === listing.id ? (
                                                    <>
                                                        <Button variant="ghost" size="icon" className="text-persimmon-600 hover:text-persimmon-700" onClick={handleSaveEdit} aria-label="Save changes">
                                                            <Save size={18} />
                                                        </Button>
                                                        <Button variant="ghost" size="icon" className="text-stone-500 hover:text-ink-800" onClick={handleCancelEdit} aria-label="Cancel editing">
                                                            <X size={18} />
                                                        </Button>
                                                    </>
                                                ) : (
                                                    <>
                                                        <Button variant="ghost" size="icon" className="text-stone-500 hover:text-ink-800" onClick={() => handleEdit(listing)} aria-label="Edit listing">
                                                            <Edit3 size={18} />
                                                        </Button>
                                                        <Button variant="ghost" size="icon" className="text-stone-500 hover:text-red-600 hover:bg-red-50" onClick={() => setPendingDeleteId(listing.id)} aria-label="Remove listing">
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

            <Dialog open={pendingDeleteId !== null} onOpenChange={(open) => { if (!open) setPendingDeleteId(null) }}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Delete this listing?</DialogTitle>
                        <DialogDescription>
                            This removes the listing and its source folder from disk. It can't be undone.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="gap-2 sm:gap-2">
                        <Button variant="outline" onClick={() => setPendingDeleteId(null)}>Cancel</Button>
                        <Button variant="destructive" onClick={confirmDelete}>Delete</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
