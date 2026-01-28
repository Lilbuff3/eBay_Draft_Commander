
import { useState, useRef, useEffect, useReducer } from 'react'
import { Trash2, Search, Package } from 'lucide-react'
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
    fullData?: any // Store the full API response for drafting
}

type BatchAction =
    | { type: 'ADD_ITEM'; payload: { id: string; isbn: string } }
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
                condition: 'Used - Good', // Default assumption
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
    } catch (e) {
        return []
    }
}

export function BatchScan() {
    const [items, dispatch] = useReducer(batchReducer, [], initBatchState)
    const [isProcessing, setIsProcessing] = useState(false)

    // Persistence Effect
    useEffect(() => {
        localStorage.setItem('batchScanItems', JSON.stringify(items))
    }, [items])


    // Scanner Refs
    const bufferRef = useRef('')
    const lastKeystrokeRef = useRef(0)
    const [lastScannedId, setLastScannedId] = useState<string | null>(null)

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
                if (isbn.length >= 10 && /^\d+$/.test(isbn)) {
                    console.log("Batch Scan:", isbn)
                    await handleScan(isbn)
                }
                bufferRef.current = ''
            } else if (e.key.length === 1) {
                bufferRef.current += e.key
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [])

    // --- Logic ---
    const handleScan = async (isbn: string) => {
        const id = crypto.randomUUID()
        dispatch({ type: 'ADD_ITEM', payload: { id, isbn } })
        setLastScannedId(id) // Highlight effect?

        try {
            const res = await fetch(`http://localhost:5000/api/lookup/book?isbn=${isbn}`)
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
                new Audio('/sounds/success.mp3').play().catch(() => { }) // Placeholder for sound
            } else {
                dispatch({
                    type: 'UPDATE_ITEM',
                    payload: { id, data: { title: 'Book Not Found', status: 'not_found' } }
                })
                new Audio('/sounds/error.mp3').play().catch(() => { })
            }
        } catch (e) {
            dispatch({
                type: 'UPDATE_ITEM',
                payload: { id, data: { title: 'Lookup Error', status: 'error' } }
            })
        }
    }

    const handleDraftAll = async () => {
        setIsProcessing(true)
        const validItems = items.filter(i => i.status === 'found')

        let processed = 0
        for (const item of validItems) {
            dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { status: 'drafting' } } })

            try {
                // Simulating the API call for MVP
                await new Promise(r => setTimeout(r, 800))

                dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { status: 'drafted', listingId: 'DRAFT-' + item.isbn } } })
            } catch (e) {
                dispatch({ type: 'UPDATE_ITEM', payload: { id: item.id, data: { status: 'error' } } })
            }
            processed++
        }
        setIsProcessing(false)
        toast.success(`Processed ${processed} items!`)
    }

    // --- Render ---
    return (
        <div className="flex flex-col h-full bg-stone-50 p-6">
            {/* Header */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-stone-800 flex items-center gap-2">
                        <Package className="text-blue-600" />
                        Batch Scanner
                    </h1>
                    <p className="text-sm text-stone-500">Scan books rapidly to build your queue.</p>
                </div>

                <div className="flex gap-3">
                    <Button variant="outline" onClick={() => dispatch({ type: 'CLEAR_ALL' })}>
                        <Trash2 size={16} className="mr-2" /> Clear
                    </Button>
                    <Button
                        onClick={handleDraftAll}
                        disabled={isProcessing || items.filter(i => i.status === 'found').length === 0}
                        className="bg-blue-600 hover:bg-blue-700 text-white"
                    >
                        {isProcessing ? 'Processing...' : `Draft All (${items.filter(i => i.status === 'found').length})`}
                    </Button>
                </div>
            </div>

            {/* Toolbar */}
            <div className="bg-white p-4 rounded-xl shadow-sm border border-stone-100 mb-6 flex gap-4 items-center">
                <span className="text-sm font-medium text-stone-600">Bulk Actions:</span>
                <Select onValueChange={(val) => dispatch({ type: 'SET_ALL_CONDITION', payload: val })}>
                    <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="Set Condition" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="Like New">Like New</SelectItem>
                        <SelectItem value="Very Good">Very Good</SelectItem>
                        <SelectItem value="Good">Good</SelectItem>
                        <SelectItem value="Acceptable">Acceptable</SelectItem>
                    </SelectContent>
                </Select>

                <div className="flex-1" />

                <div className="flex items-center gap-2 px-3 py-1 bg-green-50 text-green-700 rounded-full text-xs font-medium animate-pulse">
                    <Search size={12} /> Scanner Ready
                </div>
            </div>

            {/* Grid */}
            <div className="flex-1 bg-white rounded-xl shadow-sm border border-stone-100 overflow-hidden flex flex-col">
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
                                            <img src={item.stock_photo} className="h-12 w-auto object-contain rounded" />
                                        ) : (
                                            <div className="h-12 w-8 bg-stone-100 rounded" />
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <div className="font-medium">{item.title}</div>
                                        <div className="text-xs text-stone-500">{item.id} • {item.author}</div>
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
                                                <SelectItem value="Like New">Like New</SelectItem>
                                                <SelectItem value="Very Good">Very Good</SelectItem>
                                                <SelectItem value="Good">Good</SelectItem>
                                                <SelectItem value="Acceptable">Acceptable</SelectItem>
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
                                        {item.status === 'loading' && <Badge variant="outline" className="animate-pulse">Loading</Badge>}
                                        {item.status === 'found' && <Badge className="bg-green-100 text-green-700 border-green-200">Ready</Badge>}
                                        {item.status === 'not_found' && <Badge variant="destructive">Not Found</Badge>}
                                        {item.status === 'drafting' && <Badge className="bg-blue-100 text-blue-700">Drafting...</Badge>}
                                        {item.status === 'drafted' && <Badge className="bg-stone-800 text-white">Drafted</Badge>}
                                    </TableCell>
                                    <TableCell>
                                        <Button variant="ghost" size="icon" onClick={() => dispatch({ type: 'REMOVE_ITEM', payload: item.id })}>
                                            <Trash2 size={16} className="text-stone-400 hover:text-red-500" />
                                        </Button>
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
