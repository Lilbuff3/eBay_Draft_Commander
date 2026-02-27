import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { CheckCircle2, AlertCircle, DollarSign, Clock, ListFilter } from 'lucide-react'
import { useCommanderStore } from '@/store/useCommanderStore'

interface BatchSummaryDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    summary: {
        succeeded: number;
        failed: number;
        total_value: number;
        avg_time: number;
        total_duration: number;
    } | null
}

export function BatchSummaryDialog({
    open,
    onOpenChange,
    summary,
}: BatchSummaryDialogProps) {
    const setActiveFilter = useCommanderStore(state => state.setActiveFilter)

    if (!summary) return null

    const handleFilterToFailed = () => {
        setActiveFilter('action')
        onOpenChange(false)
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-md">
                <DialogHeader>
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-full bg-sage-100">
                            <CheckCircle2 size={24} className="text-sage-600" />
                        </div>
                        <div>
                            <DialogTitle className="text-xl font-display font-bold text-stone-800">
                                Batch Processing Complete
                            </DialogTitle>
                        </div>
                    </div>
                    <DialogDescription className="text-stone-500">
                        The batch run has finished. Here is a summary of the activity.
                    </DialogDescription>
                </DialogHeader>

                <div className="grid grid-cols-2 gap-4 my-6">
                    <div className="bg-stone-50 p-4 rounded-xl border border-stone-100">
                        <div className="flex items-center gap-2 text-stone-400 text-xs font-medium uppercase tracking-wider mb-1">
                            <CheckCircle2 size={14} className="text-green-500" />
                            Succeeded
                        </div>
                        <div className="text-2xl font-bold text-stone-800">{summary.succeeded}</div>
                    </div>
                    <div className={`p-4 rounded-xl border ${summary.failed > 0 ? 'bg-red-50 border-red-100' : 'bg-stone-50 border-stone-100'}`}>
                        <div className="flex items-center gap-2 text-stone-400 text-xs font-medium uppercase tracking-wider mb-1">
                            <AlertCircle size={14} className={summary.failed > 0 ? 'text-red-500' : 'text-stone-400'} />
                            Failed
                        </div>
                        <div className={`text-2xl font-bold ${summary.failed > 0 ? 'text-red-700' : 'text-stone-800'}`}>{summary.failed}</div>
                    </div>
                    <div className="bg-stone-50 p-4 rounded-xl border border-stone-100">
                        <div className="flex items-center gap-2 text-stone-400 text-xs font-medium uppercase tracking-wider mb-1">
                            <DollarSign size={14} className="text-blue-500" />
                            Total Value
                        </div>
                        <div className="text-2xl font-bold text-stone-800">${summary.total_value.toFixed(2)}</div>
                    </div>
                    <div className="bg-stone-50 p-4 rounded-xl border border-stone-100">
                        <div className="flex items-center gap-2 text-stone-400 text-xs font-medium uppercase tracking-wider mb-1">
                            <Clock size={14} className="text-amber-500" />
                            Avg Time
                        </div>
                        <div className="text-2xl font-bold text-stone-800">{summary.avg_time}s</div>
                    </div>
                </div>

                <DialogFooter className="flex-col gap-2 sm:flex-col">
                    {summary.failed > 0 && (
                        <Button 
                            variant="outline" 
                            className="w-full justify-center gap-2 text-red-600 border-red-100 hover:bg-red-50"
                            onClick={handleFilterToFailed}
                        >
                            <ListFilter size={18} />
                            View Failed Items
                        </Button>
                    )}
                    <Button 
                        className="w-full justify-center bg-stone-800 hover:bg-stone-900 text-white"
                        onClick={() => onOpenChange(false)}
                    >
                        Dismiss
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
串串
