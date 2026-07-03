
import { useState, useRef, useEffect, useReducer, useCallback } from 'react'
import { Trash2, Search, Package, ImagePlus, Camera } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { fetchWithKey, createJobFromMetadata, startQueue, type CreateFromMetadataPayload } from '@/lib/api'
import { normalizeIsbn, isLikelyIsbn, ScanDeduper, playScanBeep } from '@/lib/isbn'
import { CameraBarcodeScanner } from '@/components/CameraBarcodeScanner'
import { useCommanderStore } from '@/store/useCommanderStore'

export const CONDITION_OPTIONS = [
    { value: 'NEW', label: 'New' },
    { value: 'NEW_OTHER', label: 'New - Open Box' },
    { value: 'LIKE_NEW', label: 'Like New' },
    { value: 'USED_EXCELLENT', label: 'Used - Excellent' },
    { value: 'USED_VERY_GOOD', label: 'Used - Very Good' },
    { value: 'USED_GOOD', label: 'Used - Good' },
    { value: 'USED_ACCEPTABLE', label: 'Used - Acceptable' },
] as const

function ConditionItems() {
    return (
        <>
            {CONDITION_OPTIONS.map(o => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
        </>
    )
}


// --- Types ---
interface BatchItem {
    id: string
    isbn: string
    title: string
    author: string
    condition: string
    price: string
    status: 'loading' | 'found' | 'not_found' | 'error' | 'drafting' | 'drafted'
    stock_photo?: string
    imgUrl?: string
    listingId?: string
    fullData?: Record<string, unknown> // Store the full API response for drafting
}

type BatchAction =
    | { type: 'ADD_ITEM'; payload: { id: string; isbn: string; condition: string } }
    | { type: 'UPDATE_ITEM'; payload: { id: string; data: Partial<BatchItem> } }
    | { type: 'REMOVE_ITEM'; payload: string }
    | { type: 'SET_ALL_CONDITION'; payload: string }
    | { type: 'CLEAR_ALL' }

const batchReducer = (state: BatchItem[], action: BatchAction): BatchItem[] => {
    switch (action.type) {
        case 'ADD_ITEM':
            return [{
                id: action.payload.id,
                isbn: action.payload.isbn,
                title: 'Looking up...',
                author: '',
                condition: action.payload.condition, // Session condition at scan time
                price: '',
                status: 'loading'
            }, ...state]
        case 'UPDATE_ITEM':
            return state.map(item =>
                item.id === action.payload.id ? { ...item, ...action.payload.data } : item
            )
        case 'REMOVE_ITEM':
            return state.filter(item => item.id !== action.payload)
        case 'SET_ALL_CONDITION':
            return state.map(item => ({ ...item, condition: action.payload }))
        case 'CLEAR_ALL':
            return []
        default:
            return state
    }
}

// Initializer
const initBatchState = (): BatchItem[] => {
    try {
        const saved = localStorage.getItem('batchScanItems')
        return saved ? JSON.parse(saved) : []
    } catch {
        return []
    }
}

// --- Status Badge Component ---
function StatusBadge({ status }: { status: BatchItem['status'] }) {
    switch (status) {
        case 'loading': return <Badge variant="outline" className="animate-pulse">Loading</Badge>
        case 'found': return <Badge className="bg-green-100 text-green-700 border-green-200">Ready</Badge>
        case 'not_found': return <Badge variant="destructive">Not Found</Badge>
        case 'drafting': return <Badge className="bg-blue-100 text-blue-700">Drafting...</Badge>
        case 'drafted': return <Badge className="bg-stone-800 text-white">Drafted</Badge>
        case 'error': return <Badge variant="destructive">Error</Badge>
        default: return null
    }
}

// --- Mobile Card Component ---
function PhotoAttachButton({ hasPhoto, onAttach, compact }: {
    hasPhoto: boolean
    onAttach: (file: File) => void
    compact?: boolean
}) {
    const inputRef = useRef<HTMLInputElement>(null)
    return (
        <>
            <input
                ref={inputRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) onAttach(f)
                    e.target.value = ''
                }}
            />
            <Button
                variant="ghost"
                size={compact ? 'icon' : 'sm'}
                className={compact ? 'h-8 w-8 flex-shrink-0' : 'h-8'}
                onClick={() => inputRef.current?.click()}
                title={hasPhoto ? 'Photo attached — tap to replace' : 'Add a real photo (optional)'}
            >
                <ImagePlus size={14} className={hasPhoto ? 'text-green-600' : 'text-stone-400'} />
            </Button>
        </>
    )
}

function BatchItemCard({
    item,
    isHighlighted,
    hasPhoto,
    onUpdateCondition,
    onUpdatePrice,
    onRemove,
    onAttachPhoto,
}: {
    item: BatchItem
    isHighlighted: boolean
    hasPhoto: boolean
    onUpdateCondition: (val: string) => void
    onUpdatePrice: (val: string) => void
    onRemove: () => void
    onAttachPhoto: (file: File) => void
}) {
    return (
        <div className={`bg-white rounded-xl border p-3 transition-colors ${isHighlighted ? 'border-blue-300 bg-blue-50/50' : 'border-stone-200'}`}>
            <div className="flex gap-3">
                {/* Cover Image */}
                <div className="flex-shrink-0">
                    {item.stock_photo ? (
                        <img src={item.stock_photo} alt={item.title || "Book cover"} className="h-16 w-12 object-cover rounded-lg" />
                    ) : (
                        <div className="h-16 w-12 bg-stone-100 rounded-lg" />
                    )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                            <h4 className="font-medium text-sm text-stone-800 line-clamp-2 leading-snug">{item.title}</h4>
                            <p className="text-xs text-stone-400 mt-0.5 truncate">{item.isbn} {item.author && `• ${item.author}`}</p>
                        </div>
                        <StatusBadge status={item.status} />
                    </div>

                    {/* Price + Condition row */}
                    <div className="flex items-center gap-2 mt-2">
                        <div className="relative flex-1">
                            <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-stone-400">$</span>
                            <Input
                                className="h-8 pl-5 text-sm"
                                value={item.price}
                                onChange={(e) => onUpdatePrice(e.target.value)}
                                placeholder="0.00"
                            />
                        </div>
                        <Select value={item.condition} onValueChange={onUpdateCondition}>
                            <SelectTrigger className="h-8 flex-1 text-xs">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <ConditionItems />
                            </SelectContent>
                        </Select>
                        <PhotoAttachButton compact hasPhoto={hasPhoto} onAttach={onAttachPhoto} />
                        <Button variant="ghost" size="icon" className="h-8 w-8 flex-shrink-0" onClick={onRemove}>
                            <Trash2 size={14} className="text-stone-400" />
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    )
}


export function BatchScan() {
    const [items, dispatch] = useReducer(batchReducer, [], initBatchState)
    const [isProcessing, setIsProcessing] = useState(false)
    const handlePhotoFlow = useCommanderStore(s => s.handleScan)

    // Condition session: every new scan inherits this until you change it —
    // scan the New pile, switch, scan the Very Good pile.
    const [sessionCondition, setSessionCondition] = useState(() => {
        try { return localStorage.getItem('batchScanSessionCondition') || 'USED_GOOD' } catch { return 'USED_GOOD' }
    })
    useEffect(() => {
        try { localStorage.setItem('batchScanSessionCondition', sessionCondition) } catch { /* non-persistent */ }
    }, [sessionCondition])
    const sessionConditionRef = useRef(sessionCondition)
    useEffect(() => { sessionConditionRef.current = sessionCondition }, [sessionCondition])

    // Optional real photo per item. Files aren't JSON-serializable, so these
    // live outside the persisted reducer — a page reload drops them.
    const photosRef = useRef(new Map<string, File>())
    const [photoVersion, setPhotoVersion] = useState(0) // re-render on attach

    // Persistence Effect
    useEffect(() => {
        localStorage.setItem('batchScanItems', JSON.stringify(items))
    }, [items])


    // Scanner Refs
    const bufferRef = useRef('')
    const lastKeystrokeRef = useRef(0)
    const deduperRef = useRef(new ScanDeduper(3000))
    const [lastScannedId, setLastScannedId] = useState<string | null>(null)

    // --- Logic ---
    const handleScan = useCallback(async (rawIsbn: string) => {
        const isbn = normalizeIsbn(rawIsbn)
        if (!isLikelyIsbn(isbn)) {
            playScanBeep('error')
            return
        }
        if (!deduperRef.current.shouldAccept(isbn)) return // camera re-read / double-Enter

        const id = crypto.randomUUID()
        dispatch({ type: 'ADD_ITEM', payload: { id, isbn, condition: sessionConditionRef.current } })
        setLastScannedId(id)

        try {
            const res = await fetchWithKey(`/api/lookup/book?isbn=${isbn}`)
            const data = await res.json()

            if (data.success) {
                dispatch({
                    type: 'UPDATE_ITEM',
                    payload: {
                        id,
                        data: {
                            title: data.title,
                            author: data.item_specifics?.Author || '',
                            price: data.price?.toString() || '',
                            stock_photo: data.stock_photo,
                            status: 'found',
                            fullData: data // Store for drafting
                        }
                    }
                })
                playScanBeep('success')
            } else {
                dispatch({
                    type: 'UPDATE_ITEM',
                    payload: { id, data: { title: 'Book Not Found', status: 'not_found' } }
                })
                playScanBeep('error')
            }
        } catch {
            dispatch({
                type: 'UPDATE_ITEM',
                payload: { id, data: { title: 'Lookup Error', status: 'error' } }
            })
        }
    }, [dispatch])

    const attachPhoto = useCallback((itemId: string, file: File) => {
        photosRef.current.set(itemId, file)
        setPhotoVersion(v => v + 1)
        toast.success('Photo attached — it will upload with the draft')
    }, [])

    // --- Scanner Listener ---
    useEffect(() => {
        const handleKeyDown = async (e: KeyboardEvent) => {
            // Allow typing in inputs
            const target = e.target as HTMLElement
            if (['INPUT', 'TEXTAREA'].includes(target.tagName) || target.isContentEditable) return

            const now = Date.now()
            if (now - lastKeystrokeRef.current > 50) bufferRef.current = ''
            lastKeystrokeRef.current = now

            if (e.key === 'Enter') {
                const isbn = bufferRef.current
                if (isLikelyIsbn(isbn)) {
                    await handleScan(isbn)
                }
                bufferRef.current = ''
            } else if (e.key.length === 1) {
                bufferRef.current += e.key
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [handleScan])

    const handleDraftAll = async () => {
        setIsProcessing(true)
        const validItems = items.filter(i => i.status === 'found')

        let successCount = 0
        let errorCount = 0
        const noCoverTitles: string[] = []
        for (const item of validItems) {
            dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { status: 'drafting' } } })

            try {
                const payload: CreateFromMetadataPayload = {
                    title: item.title,
                    isbn: item.isbn,
                    description: String(item.fullData?.description || ''),
                    thumbnail: item.stock_photo || '',
                    condition: item.condition,
                    price: item.price || undefined,
                    category_id: item.fullData?.category_id as string | undefined,
                    item_specifics: item.fullData?.item_specifics as Record<string, unknown> | undefined,
                    pricing_data: item.fullData?.pricing_data as Record<string, unknown> | undefined,
                    // The user just reviewed this row — don't bounce it back
                    // through the price-sanity review queue.
                    user_approved: true,
                    source: 'batch_scan',
                }
                const data = await createJobFromMetadata(payload, photosRef.current.get(item.id))

                if (data.success) {
                    dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { status: 'drafted', listingId: data.jobId } } })
                    if (data.cover === false && !photosRef.current.has(item.id)) {
                        noCoverTitles.push(item.title)
                    }
                    photosRef.current.delete(item.id)
                    successCount++
                } else {
                    dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { status: 'error' } } })
                    errorCount++
                }
            } catch {
                dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { status: 'error' } } })
                errorCount++
            }
        }

        // Start the queue only after every draft (and its photo) is in place
        if (successCount > 0) {
            try { await startQueue() } catch { /* queue may already be running */ }
        }

        setIsProcessing(false)
        if (noCoverTitles.length > 0) {
            toast.warning(`No cover found for: ${noCoverTitles.join(', ')} — add a photo or they can't list.`, { duration: 10000 })
        }
        if (errorCount === 0) {
            toast.success(`Drafted ${successCount} items — queue started!`)
        } else {
            toast.warning(`Drafted ${successCount} items, ${errorCount} failed.`)
        }
    }

    const foundCount = items.filter(i => i.status === 'found').length

    // --- Render ---
    return (
        <div className="flex flex-col h-full bg-stone-50 p-4 sm:p-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-4 sm:mb-6">
                <div>
                    <h1 className="text-xl sm:text-2xl font-bold text-stone-800 flex items-center gap-2">
                        <Package className="text-blue-600" />
                        Batch Scanner
                    </h1>
                    <p className="text-sm text-stone-500">Scan books rapidly to build your queue.</p>
                </div>

                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => dispatch({ type: 'CLEAR_ALL' })}>
                        <Trash2 size={14} className="mr-1.5" /> Clear
                    </Button>
                    <Button
                        size="sm"
                        onClick={handleDraftAll}
                        disabled={isProcessing || foundCount === 0}
                        className="bg-blue-600 hover:bg-blue-700 text-white"
                    >
                        {isProcessing ? 'Processing...' : `Draft All (${foundCount})`}
                    </Button>
                </div>
            </div>

            {/* Session condition — every new scan inherits this */}
            <div className="bg-persimmon-50 border border-persimmon-100 p-3 sm:p-4 rounded-xl mb-3 flex flex-wrap gap-3 items-center">
                <span className="text-sm font-semibold text-persimmon-700">Scanning as:</span>
                <Select value={sessionCondition} onValueChange={setSessionCondition}>
                    <SelectTrigger className="w-[170px] sm:w-[190px] h-8 bg-white">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <ConditionItems />
                    </SelectContent>
                </Select>
                <span className="text-xs text-persimmon-600/80 hidden sm:inline">
                    Scan a pile, switch condition, scan the next pile.
                </span>
                <div className="flex-1" />
                <div className="flex items-center gap-2 px-3 py-1 bg-green-50 text-green-700 rounded-full text-xs font-medium animate-pulse">
                    <Search size={12} /> Scanner Ready
                </div>
            </div>

            {/* Toolbar: camera + bulk actions */}
            <div className="bg-white p-3 sm:p-4 rounded-xl shadow-sm border border-stone-100 mb-4 sm:mb-6 flex flex-wrap gap-3 items-center">
                <CameraBarcodeScanner onDetect={handleScan} />
                <div className="flex-1" />
                <span className="text-sm font-medium text-stone-600">Set all:</span>
                <Select onValueChange={(val) => dispatch({ type: 'SET_ALL_CONDITION', payload: val })}>
                    <SelectTrigger className="w-[160px] sm:w-[180px] h-8">
                        <SelectValue placeholder="Condition" />
                    </SelectTrigger>
                    <SelectContent>
                        <ConditionItems />
                    </SelectContent>
                </Select>
            </div>

            {/* Mobile Card List (visible on small screens) */}
            <div className="flex-1 overflow-auto md:hidden">
                {items.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 text-stone-400">
                        <Search size={48} className="opacity-20 mb-2" />
                        <p>Scan an ISBN to start...</p>
                        <button
                            onClick={() => void handlePhotoFlow()}
                            className="mt-3 text-xs text-blue-500 hover:underline inline-flex items-center gap-1"
                        >
                            <Camera size={12} /> No barcode? Use photo capture instead
                        </button>
                    </div>
                ) : (
                    <div className="space-y-2 pb-4">
                        {items.map((item) => (
                            <BatchItemCard
                                key={item.id}
                                item={item}
                                isHighlighted={item.id === lastScannedId}
                                hasPhoto={photoVersion >= 0 && photosRef.current.has(item.id)}
                                onUpdateCondition={(val) => dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { condition: val } } })}
                                onUpdatePrice={(val) => dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { price: val } } })}
                                onRemove={() => dispatch({ type: 'REMOVE_ITEM', payload: item.id })}
                                onAttachPhoto={(file) => attachPhoto(item.id, file)}
                            />
                        ))}
                    </div>
                )}
                <div className="py-2 text-xs text-center text-stone-400">
                    {items.length} items in batch
                </div>
            </div>

            {/* Desktop Table (visible on md+) */}
            <div className="hidden md:flex flex-1 bg-white rounded-xl shadow-sm border border-stone-100 overflow-hidden flex-col">
                <div className="overflow-auto flex-1">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-[80px]">Cover</TableHead>
                                <TableHead>Book Details</TableHead>
                                <TableHead className="w-[200px]">Condition</TableHead>
                                <TableHead className="w-[150px]">Market Price</TableHead>
                                <TableHead className="w-[100px]">Status</TableHead>
                                <TableHead className="w-[50px]"></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {items.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={6} className="h-64 text-center text-stone-400">
                                        <div className="flex flex-col items-center gap-2">
                                            <Search size={48} className="opacity-20" />
                                            <p>Scan an ISBN to start...</p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            )}
                            {items.map((item) => (
                                <TableRow key={item.id} className={item.id === lastScannedId ? "bg-blue-50/50" : ""}>
                                    <TableCell>
                                        {item.stock_photo ? (
                                            <img src={item.stock_photo} alt={item.title || "Book cover"} className="h-12 w-auto object-contain rounded" />
                                        ) : (
                                            <div className="h-12 w-8 bg-stone-100 rounded" />
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <div className="font-medium">{item.title}</div>
                                        <div className="text-xs text-stone-500">{item.isbn} • {item.author}</div>
                                    </TableCell>
                                    <TableCell>
                                        <Select
                                            value={item.condition}
                                            onValueChange={(val) => dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { condition: val } } })}
                                        >
                                            <SelectTrigger className="h-8">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <ConditionItems />
                                            </SelectContent>
                                        </Select>
                                    </TableCell>
                                    <TableCell>
                                        <div className="relative">
                                            <span className="absolute left-2 top-1.5 text-xs text-stone-400">$</span>
                                            <Input
                                                className="h-8 pl-5"
                                                value={item.price}
                                                onChange={(e) => dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { price: e.target.value } } })}
                                            />
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <StatusBadge status={item.status} />
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center">
                                            <PhotoAttachButton
                                                compact
                                                hasPhoto={photoVersion >= 0 && photosRef.current.has(item.id)}
                                                onAttach={(file) => attachPhoto(item.id, file)}
                                            />
                                            <Button variant="ghost" size="icon" onClick={() => dispatch({ type: 'REMOVE_ITEM', payload: item.id })}>
                                                <Trash2 size={16} className="text-stone-400 hover:text-red-500" />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
                <div className="p-2 bg-stone-50 border-t border-stone-100 text-xs text-center text-stone-400">
                    {items.length} items in batch
                </div>
            </div>
        </div>
    )
}
