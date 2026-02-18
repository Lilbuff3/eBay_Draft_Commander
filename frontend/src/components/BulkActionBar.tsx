import { Trash2, DollarSign, Tag, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

interface BulkActionBarProps {
    selectedCount: number
    onClearSelection: () => void
    onDelete: () => void
    onUpdatePrice: () => void
    onSetCondition: () => void
}

export function BulkActionBar({
    selectedCount,
    onClearSelection,
    onDelete,
    onUpdatePrice,
    onSetCondition
}: BulkActionBarProps) {
    if (selectedCount === 0) return null

    return (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-full max-w-2xl px-4 animate-in slide-in-from-bottom-10 fade-in duration-300">
            <Card className="bg-slate-900/90 backdrop-blur-md border-slate-700 text-white p-3 shadow-2xl flex items-center justify-between gap-4 rounded-full px-6">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <span className="bg-blue-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                            {selectedCount}
                        </span>
                        <span className="text-sm font-medium text-slate-300">Selected</span>
                    </div>

                    <div className="h-4 w-px bg-slate-700 mx-2" />

                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 text-slate-300 hover:text-white hover:bg-slate-800"
                            onClick={onSetCondition}
                        >
                            <Tag size={14} className="mr-2" />
                            Condition
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 text-slate-300 hover:text-white hover:bg-slate-800"
                            onClick={onUpdatePrice}
                        >
                            <DollarSign size={14} className="mr-2" />
                            Price
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 text-red-400 hover:text-red-300 hover:bg-red-950/30"
                            onClick={onDelete}
                        >
                            <Trash2 size={14} className="mr-2" />
                            Delete
                        </Button>
                    </div>
                </div>

                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-full hover:bg-slate-800 text-slate-400"
                    onClick={onClearSelection}
                >
                    <X size={16} />
                </Button>
            </Card>
        </div>
    )
}
