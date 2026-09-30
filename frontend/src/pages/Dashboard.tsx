import { useCallback, useEffect } from 'react'
import { toast } from 'sonner'
import { ItemDetailDrawer } from '@/components/ItemDetailDrawer'
import { ScannerListener, type ScannedBook } from '@/components/ScannerListener'
import { useCommanderStore } from '@/store/useCommanderStore'
import { useQueryClient } from '@tanstack/react-query'
import { BatchSummaryDialog } from '@/components/BatchSummaryDialog'
import { DashboardHome } from '@/home/DashboardHome'

export function Dashboard() {
    const queryClient = useQueryClient()

    // Store State
    const setActiveTab = useCommanderStore(state => state.setActiveTab)
    const lastUploadedJobId = useCommanderStore(state => state.lastUploadedJobId)
    const setLastUploadedJobId = useCommanderStore(state => state.setLastUploadedJobId)
    const batchSummary = useCommanderStore(state => state.batchSummary)
    const setBatchSummary = useCommanderStore(state => state.setBatchSummary)

    // Mobile upload landed: refresh the jobs list and get out of the way. The
    // capture sheet's success interstitial ("Item #N on its way → Snap next
    // item") owns all feedback now — a toast on top of it was double noise, and
    // its Review action opened the drawer underneath the still-open sheet.
    // Review happens in a batch later from the workspace; that's the momentum
    // philosophy: snap → next item.
    useEffect(() => {
        if (!lastUploadedJobId) return
        setLastUploadedJobId(null)
        queryClient.invalidateQueries({ queryKey: ['jobs'] })
    }, [lastUploadedJobId, setLastUploadedJobId, queryClient])

    // A wedge scan on the home screen queues the book into the Books tab
    // (same localStorage handoff Sourcing's "Send to Books" uses — BatchScan
    // reads 'batchScanItems' on mount).
    const handleWedgeScan = useCallback((book: ScannedBook) => {
        try {
            const saved = localStorage.getItem('batchScanItems')
            const items: unknown[] = saved ? JSON.parse(saved) : []
            let condition = 'USED_GOOD'
            try { condition = localStorage.getItem('batchScanSessionCondition') || 'USED_GOOD' } catch { /* default */ }
            items.unshift({
                id: crypto.randomUUID(),
                isbn: book.isbn,
                title: book.title,
                author: book.item_specifics?.Author || '',
                condition,
                price: book.price?.toString() || '',
                status: 'found',
                stock_photo: book.stock_photo,
                fullData: book,
            })
            localStorage.setItem('batchScanItems', JSON.stringify(items))
            toast.success('Queued in Books tab', {
                description: book.title,
                action: { label: 'Open Books', onClick: () => setActiveTab('batch-scan') },
            })
        } catch {
            toast.error('Could not queue scan — Books list storage full?')
        }
    }, [setActiveTab])

    return (
        <div className="flex-1 flex flex-col h-full overflow-hidden relative">
            {/* Hardware barcode scanner: listens globally for rapid keystrokes */}
            <ScannerListener onScan={handleWedgeScan} />

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto">
                <DashboardHome userName="Adam" />
            </div>

            {/* Detail Drawer */}
            <ItemDetailDrawer />

            {/* Batch Summary */}
            <BatchSummaryDialog
                open={!!batchSummary}
                onOpenChange={(open) => !open && setBatchSummary(null)}
                summary={batchSummary}
            />
        </div>
    )
}
