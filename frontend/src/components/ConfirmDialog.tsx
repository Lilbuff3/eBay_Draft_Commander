import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { AlertTriangle, Trash2, FolderX } from 'lucide-react'

interface ConfirmDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    title: string
    description: string
    count?: number
    /** Show the "Also delete folders" option */
    showFolderOption?: boolean
    onConfirm: (deleteFolders: boolean) => void
    confirmLabel?: string
    destructive?: boolean
}

export function ConfirmDialog({
    open,
    onOpenChange,
    title,
    description,
    count,
    showFolderOption = false,
    onConfirm,
    confirmLabel = 'Delete',
    destructive = true,
}: ConfirmDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-full ${destructive ? 'bg-red-100' : 'bg-stone-100'}`}>
                            <AlertTriangle size={20} className={destructive ? 'text-red-600' : 'text-stone-600'} />
                        </div>
                        <div>
                            <DialogTitle className="text-base">
                                {title}
                                {count !== undefined && count > 0 && (
                                    <span className="ml-1.5 text-stone-400 font-normal">({count})</span>
                                )}
                            </DialogTitle>
                        </div>
                    </div>
                    <DialogDescription className="mt-2 text-sm">
                        {description}
                    </DialogDescription>
                </DialogHeader>

                <DialogFooter className="flex-col gap-2 sm:flex-col mt-2">
                    {showFolderOption && (
                        <Button
                            variant="destructive"
                            className="w-full justify-center gap-2"
                            onClick={() => { onConfirm(true); onOpenChange(false) }}
                        >
                            <FolderX size={16} />
                            {confirmLabel} + Remove Folders
                        </Button>
                    )}
                    <Button
                        variant={destructive ? 'outline' : 'default'}
                        className={`w-full justify-center gap-2 ${destructive && !showFolderOption ? 'bg-red-600 hover:bg-red-700 text-white border-red-600' : destructive ? 'text-red-600 border-red-200 hover:bg-red-50' : ''}`}
                        onClick={() => { onConfirm(false); onOpenChange(false) }}
                    >
                        <Trash2 size={16} />
                        {showFolderOption ? `${confirmLabel} from App Only` : confirmLabel}
                    </Button>
                    <Button
                        variant="ghost"
                        className="w-full justify-center text-stone-500"
                        onClick={() => onOpenChange(false)}
                    >
                        Cancel
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
