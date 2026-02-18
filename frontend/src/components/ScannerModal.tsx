import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Loader2, Search, Plus } from 'lucide-react'
import { lookupBook, createJobFromMetadata } from '@/lib/api'
import { toast } from 'sonner'

interface ScannerModalProps {
    isOpen: boolean
    onOpenChange: (open: boolean) => void
    onJobCreated: () => void
}

export function ScannerModal({ isOpen, onOpenChange, onJobCreated }: ScannerModalProps) {
    const [isbn, setIsbn] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [result, setResult] = useState<any>(null)
    const [isCreating, setIsCreating] = useState(false)

    const handleLookup = async () => {
        if (!isbn) return

        setIsLoading(true)
        setResult(null)
        try {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const data = await lookupBook(isbn) as any
            if (data.success) {
                setResult(data)
            } else {
                toast.error(data.error || 'Book not found')
            }
        } catch { // Removed 'error' variable as it was unused
            toast.error('Lookup failed')
        } finally {
            setIsLoading(false)
        }
    }

    const handleCreateJob = async () => {
        if (!result) return

        setIsCreating(true)
        try {
            const res = await createJobFromMetadata(result)
            if (res.success) {
                toast.success('Job created successfully')
                onJobCreated()
                onOpenChange(false)
                setResult(null)
                setIsbn('')
            } else {
                toast.error(res.error || 'Failed to create job')
            }
        } catch { // Removed 'error' variable as it was unused
            toast.error('Creation failed')
        } finally {
            setIsCreating(false)
        }
    }

    return (
        <Dialog open={isOpen} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Add Item via ISBN</DialogTitle>
                    <DialogDescription>
                        Enter an ISBN to look up book details and create a listing draft.
                    </DialogDescription>
                </DialogHeader>

                <div className="flex flex-col gap-4 py-4">
                    <div className="flex gap-2">
                        <Input
                            placeholder="Enter ISBN (e.g. 9780131103627)"
                            value={isbn}
                            onChange={(e) => setIsbn(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleLookup()}
                        />
                        <Button onClick={handleLookup} disabled={isLoading || !isbn}>
                            {isLoading ? <Loader2 className="animate-spin" /> : <Search size={18} />}
                        </Button>
                    </div>

                    {result && (
                        <div className="border rounded-md p-4 bg-muted/30 flex gap-4 animate-in fade-in slide-in-from-top-2">
                            {result.thumbnail && (
                                <img src={result.thumbnail} alt="Cover" className="h-32 w-24 object-cover rounded shadow-sm bg-white" />
                            )}
                            <div className="flex-1 space-y-1">
                                <h3 className="font-semibold text-lg leading-tight">{result.title}</h3>
                                <p className="text-sm text-muted-foreground">{result.authors?.join(', ')}</p>
                                <div className="text-xs text-muted-foreground mt-2">
                                    <p>{result.publisher} • {result.publishedDate}</p>
                                    <p>ISBN: {result.isbn}</p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button onClick={handleCreateJob} disabled={!result || isCreating || isLoading}>
                        {isCreating ? <Loader2 className="animate-spin mr-2" /> : <Plus className="mr-2" size={16} />}
                        Create Draft
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
