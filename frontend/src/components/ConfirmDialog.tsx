
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { AlertTriangle, Trash2, FolderX } from 'lucide-react'
import { useHaptics } from '@/hooks/useHaptics'
import { useIsMobile } from '@/hooks/useIsMobile'

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

function ConfirmContent({
    title,
    description,
    count,
    showFolderOption,
    onConfirm,
    onOpenChange,
    confirmLabel,
    destructive,
}: Omit<ConfirmDialogProps, 'open'>) {
    const { warning, tap } = useHaptics()

    const handleConfirm = (deleteFolders: boolean) => {
        warning()
        onConfirm(deleteFolders)
        onOpenChange(false)
    }

    return (
        <>
            {/* Icon + Title */}
            <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-full ${destructive ? 'bg-red-100' : 'bg-stone-100'}`}>
                    <AlertTriangle size={22} className={destructive ? 'text-red-600' : 'text-stone-600'} />
                </div>
                <div>
                    <div className="text-base font-semibold">
                        {title}
                        {count !== undefined && count > 0 && (
                            <span className="ml-1.5 text-stone-400 font-normal">({count})</span>
                        )}
                    </div>
                </div>
            </div>
            <p className="mt-2 text-sm text-stone-500">
                {description}
            </p>

            {/* Actions */}
            <div className="flex flex-col gap-2 mt-4">
                {showFolderOption && (
                    <Button
                        variant="destructive"
                        className="w-full justify-center gap-2 min-h-[48px] rounded-xl font-semibold"
                        onClick={() => handleConfirm(true)}
                    >
                        <FolderX size={16} />
                        {confirmLabel} + Remove Folders
                    </Button>
                )}
                <Button
                    variant={destructive ? 'outline' : 'default'}
                    className={`w-full justify-center gap-2 min-h-[48px] rounded-xl font-semibold ${destructive && !showFolderOption ? 'bg-red-600 hover:bg-red-700 text-white border-red-600' : destructive ? 'text-red-600 border-red-200 hover:bg-red-50' : ''}`}
                    onClick={() => handleConfirm(false)}
                >
                    <Trash2 size={16} />
                    {showFolderOption ? `${confirmLabel} from App Only` : confirmLabel}
                </Button>
                <Button
                    variant="ghost"
                    className="w-full justify-center text-stone-500 min-h-[48px] rounded-xl font-semibold"
                    onClick={() => { tap(); onOpenChange(false) }}
                >
                    Cancel
                </Button>
            </div>
        </>
    )
}

export function ConfirmDialog(props: ConfirmDialogProps) {
    const {
        open,
        onOpenChange,
        confirmLabel = 'Delete',
        destructive = true,
        showFolderOption = false,
    } = props
    const isMobile = useIsMobile()

    if (isMobile) {
        return (
            <Sheet open={open} onOpenChange={onOpenChange}>
                <SheetContent side="bottom" className="rounded-t-2xl pb-safe px-5 pt-3">
                    {/* Drag handle */}
                    <div className="flex justify-center mb-3">
                        <div className="w-10 h-1 bg-stone-300 rounded-full" />
                    </div>
                    <SheetHeader className="text-left sr-only">
                        <SheetTitle>{props.title}</SheetTitle>
                        <SheetDescription>{props.description}</SheetDescription>
                    </SheetHeader>
                    <ConfirmContent
                        {...props}
                        confirmLabel={confirmLabel}
                        destructive={destructive}
                        showFolderOption={showFolderOption}
                    />
                    <SheetFooter />
                </SheetContent>
            </Sheet>
        )
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <DialogTitle className="sr-only">{props.title}</DialogTitle>
                    <DialogDescription className="sr-only">{props.description}</DialogDescription>
                </DialogHeader>
                <ConfirmContent
                    {...props}
                    confirmLabel={confirmLabel}
                    destructive={destructive}
                    showFolderOption={showFolderOption}
                />
                <DialogFooter />
            </DialogContent>
        </Dialog>
    )
}
