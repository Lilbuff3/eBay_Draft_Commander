import { useState, useRef, useEffect, useCallback } from 'react'
import { ExternalLink, Search, Trash2, BookOpen, Loader2, ShieldCheck, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { fetchWithKey } from '@/lib/api'
import { normalizeIsbn, isLikelyIsbn, isLikelyGtin, ScanDeduper, playScanBeep } from '@/lib/isbn'
import { CameraBarcodeScanner } from '@/components/CameraBarcodeScanner'
import { CONDITION_OPTIONS } from '@/lib/conditions'
import { useHaptics } from '@/hooks/useHaptics'

// --- Types ---

type Verdict = 'BUY' | 'THIN' | 'PASS' | 'NO_DATA'

interface CompsResponse {
    success: boolean
    gtin: string
    verdict: Verdict
    max_buy: number | null
    est_sold_value: number | null
    net_proceeds: number | null
    would_list_at: number | null
    median_price: number | null
    comp_count: number
    price_range: { low: number; high: number } | null
    id_type?: 'isbn' | 'upc'
    confidence: 'high' | 'medium' | 'low' | null
    confidence_reason: string | null
    comps: Array<{ title: string; price: number; condition?: string; url?: string }>
    reasoning: string | null
    ebay_search_url: string
    error?: string
}

interface SourcingRow {
    id: string
    gtin: string
    title?: string
    condition: string
    verdict: Verdict
    maxBuy: number | null
    estSold: number | null
    ts: number
    bought?: boolean
    paid?: string
    sentToBooks?: boolean
    /** /api/lookup/book response (ISBN only) — powers Send to Books */
    bookData?: Record<string, unknown>
}

const HISTORY_KEY = 'sourcingHistory'
const HISTORY_MAX = 200
const SCAN_FORMATS = ['ean_13', 'upc_a', 'upc_e', 'ean_8']

function loadHistory(): SourcingRow[] {
    try {
        const saved = localStorage.getItem(HISTORY_KEY)
        return saved ? JSON.parse(saved) : []
    } catch {
        return []
    }
}

const usd = (n: number | null | undefined) =>
    n == null ? '—' : `$${n.toFixed(2)}`

const VERDICT_STYLE: Record<Verdict, { banner: string; chip: string; label: string }> = {
    BUY: { banner: 'bg-emerald-500/10 text-emerald-300 border-b border-white/5', chip: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20', label: 'BUY' },
    THIN: { banner: 'bg-amber-500/10 text-amber-300 border-b border-white/5', chip: 'bg-amber-500/10 text-amber-300 border-amber-500/20', label: 'THIN DATA' },
    PASS: { banner: 'bg-rose-500/10 text-rose-300 border-b border-white/5', chip: 'bg-rose-500/10 text-rose-300 border-rose-500/20', label: 'PASS' },
    NO_DATA: { banner: 'bg-slate-900/40 text-slate-300 border-b border-white/5', chip: 'bg-slate-800 text-slate-300 border-slate-700/50', label: 'NO DATA' },
}

// --- Verdict card ---

const CONFIDENCE_STYLE = {
    high: { cls: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20', Icon: ShieldCheck, label: 'Confident' },
    medium: { cls: 'bg-amber-500/10 text-amber-300 border-amber-500/20', Icon: AlertTriangle, label: 'Rough estimate' },
    low: { cls: 'bg-rose-500/10 text-rose-300 border-rose-500/20', Icon: AlertTriangle, label: 'Rough estimate' },
} as const

function ConfidenceBadge({ result }: { result: CompsResponse }) {
    if (!result.confidence) return null
    const s = CONFIDENCE_STYLE[result.confidence]
    const { Icon } = s
    return (
        <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-xs ${s.cls}`}>
            <Icon size={14} className="shrink-0 mt-0.5" />
            <div>
                <span className="font-semibold">{s.label}</span>
                {result.confidence !== 'high' && <span> — treat this as a ballpark, not a firm price</span>}
                {result.confidence_reason && <span className="opacity-80"> · {result.confidence_reason}</span>}
            </div>
        </div>
    )
}

function VerdictCard({ result, title }: { result: CompsResponse; title?: string }) {
    const style = VERDICT_STYLE[result.verdict]
    return (
        <div className="bg-slate-900/40 backdrop-blur-2xl border border-white/5 shadow-glass rounded-3xl overflow-hidden">
            <div className={`px-4 py-3 ${style.banner}`}>
                <div className="flex items-baseline justify-between gap-3">
                    <span className="text-lg font-bold tracking-wide">{style.label}</span>
                    {result.max_buy != null && result.verdict !== 'PASS' && (
                        <span className="text-2xl font-bold whitespace-nowrap">
                            pay up to {usd(result.max_buy)}
                        </span>
                    )}
                    {result.verdict === 'PASS' && (
                        <span className="text-sm opacity-90">not worth buying at any price</span>
                    )}
                </div>
                {(title || result.gtin) && (
                    <p className="text-xs opacity-80 mt-1 truncate">{title || result.gtin}</p>
                )}
            </div>

            <div className="p-4 space-y-4">
                {result.verdict === 'NO_DATA' ? (
                    <p className="text-sm text-slate-400">
                        No comps found for this barcode. Could be junk — or rare enough that nobody lists it.{' '}
                        <a href={result.ebay_search_url} target="_blank" rel="noreferrer"
                            className="text-brand-400 hover:text-brand-300 underline inline-flex items-center gap-1">
                            Search eBay <ExternalLink size={12} />
                        </a>
                    </p>
                ) : (
                    <>
                        <ConfidenceBadge result={result} />
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                            <div className="bg-slate-950/40 border border-white/5 rounded-2xl p-2.5">
                                <div className="text-[10px] font-bold tracking-wide uppercase text-slate-500">Est. sold value</div>
                                <div className="text-sm font-bold text-white mt-0.5">{usd(result.est_sold_value)}</div>
                            </div>
                            <div className="bg-slate-950/40 border border-white/5 rounded-2xl p-2.5">
                                <div className="text-[10px] font-bold tracking-wide uppercase text-slate-500">Comps</div>
                                <div className="text-sm font-bold text-white mt-0.5">
                                    {result.comp_count}
                                    {result.price_range && (
                                        <span className="font-normal text-slate-400"> ({usd(result.price_range.low)}–{usd(result.price_range.high)})</span>
                                    )}
                                </div>
                            </div>
                            <div className="bg-slate-950/40 border border-white/5 rounded-2xl p-2.5">
                                <div className="text-[10px] font-bold tracking-wide uppercase text-slate-500">Net after fees</div>
                                <div className="text-sm font-bold text-white mt-0.5">{usd(result.net_proceeds)}</div>
                            </div>
                            <div className="bg-slate-950/40 border border-white/5 rounded-2xl p-2.5">
                                <div className="text-[10px] font-bold tracking-wide uppercase text-slate-500">Would list at</div>
                                <div className="text-sm font-bold text-white mt-0.5">{usd(result.would_list_at)}</div>
                            </div>
                        </div>

                        {result.comps.length > 0 && (
                            <div className="space-y-1 bg-slate-950/20 border border-white/5 rounded-2xl p-2">
                                {result.comps.slice(0, 5).map((c, i) => (
                                    <a key={i} href={c.url} target="_blank" rel="noreferrer"
                                        className="flex items-center justify-between gap-2 text-xs text-slate-300 hover:text-brand-400 py-1 transition-colors px-1 rounded-md hover:bg-white/5">
                                        <span className="truncate">{c.title}</span>
                                        <span className="font-medium whitespace-nowrap">{usd(c.price)}</span>
                                    </a>
                                ))}
                            </div>
                        )}
                        {result.reasoning && (
                            <p className="text-[11px] text-slate-400">{result.reasoning}</p>
                        )}
                    </>
                )}
            </div>
        </div>
    )
}

// --- Page ---

export function Sourcing() {
    const [current, setCurrent] = useState<CompsResponse | null>(null)
    const [currentTitle, setCurrentTitle] = useState<string | undefined>()
    const [loading, setLoading] = useState(false)
    const [manualCode, setManualCode] = useState('')
    const [history, setHistory] = useState<SourcingRow[]>(loadHistory)
    const haptics = useHaptics()

    // Condition session — same pattern as BatchScan, separate key
    const [condition, setCondition] = useState(() => {
        try { return localStorage.getItem('sourcingCondition') || 'USED_GOOD' } catch { return 'USED_GOOD' }
    })
    useEffect(() => {
        try { localStorage.setItem('sourcingCondition', condition) } catch { /* non-persistent */ }
    }, [condition])
    const conditionRef = useRef(condition)
    useEffect(() => { conditionRef.current = condition }, [condition])

    useEffect(() => {
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, HISTORY_MAX))) } catch { /* full */ }
    }, [history])

    const deduperRef = useRef(new ScanDeduper(3000))
    const bufferRef = useRef('')
    const lastKeystrokeRef = useRef(0)

    const updateRow = useCallback((id: string, data: Partial<SourcingRow>) => {
        setHistory(prev => prev.map(r => (r.id === id ? { ...r, ...data } : r)))
    }, [])

    const handleScan = useCallback(async (raw: string) => {
        const gtin = normalizeIsbn(raw)
        if (!isLikelyGtin(gtin)) {
            playScanBeep('error')
            return
        }
        if (!deduperRef.current.shouldAccept(gtin)) return

        const cond = conditionRef.current
        const rowId = crypto.randomUUID()
        setLoading(true)
        setCurrent(null)
        setCurrentTitle(undefined)

        // Book metadata in parallel (ISBN only) — enrichment, never blocks the verdict
        const bookPromise: Promise<Record<string, unknown> | null> = isLikelyIsbn(gtin)
            ? fetchWithKey(`/api/lookup/book?isbn=${gtin}`)
                .then(r => r.json())
                .then(d => (d?.success ? d : null))
                .catch(() => null)
            : Promise.resolve(null)

        try {
            const res = await fetchWithKey(`/api/lookup/comps?gtin=${gtin}&condition=${cond}`)
            const data: CompsResponse = await res.json()
            if (!res.ok || !data.success) {
                playScanBeep('error')
                toast.error(data.error || 'Comps lookup failed')
                return
            }

            playScanBeep(data.verdict === 'BUY' ? 'success' : 'error')
            if (data.verdict === 'BUY') haptics.success()
            else if (data.verdict === 'PASS') haptics.error()
            else if (data.verdict === 'THIN') haptics.warning()
            else haptics.tap()

            const fallbackTitle = data.comps[0]?.title
            setCurrent(data)
            setCurrentTitle(fallbackTitle)
            setHistory(prev => [{
                id: rowId,
                gtin,
                title: fallbackTitle,
                condition: cond,
                verdict: data.verdict,
                maxBuy: data.max_buy,
                estSold: data.est_sold_value,
                ts: Date.now(),
            }, ...prev].slice(0, HISTORY_MAX))

            void bookPromise.then(book => {
                if (!book) return
                const bookTitle = typeof book.title === 'string' ? book.title : undefined
                if (bookTitle) {
                    setCurrentTitle(prev => prev === fallbackTitle || !prev ? bookTitle : prev)
                }
                updateRow(rowId, { title: bookTitle, bookData: book })
            })
        } catch {
            playScanBeep('error')
            toast.error('Comps lookup failed — check connection')
        } finally {
            setLoading(false)
        }
    }, [haptics, updateRow])

    // USB wedge / keyboard scanner — same guard pattern as BatchScan
    useEffect(() => {
        const handleKeyDown = async (e: KeyboardEvent) => {
            const target = e.target as HTMLElement
            if (['INPUT', 'TEXTAREA'].includes(target.tagName) || target.isContentEditable) return

            const now = Date.now()
            if (now - lastKeystrokeRef.current > 50) bufferRef.current = ''
            lastKeystrokeRef.current = now

            if (e.key === 'Enter') {
                const code = bufferRef.current
                if (isLikelyGtin(code)) await handleScan(code)
                bufferRef.current = ''
            } else if (e.key.length === 1) {
                bufferRef.current += e.key
            }
        }
        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [handleScan])

    const checkManual = () => {
        const code = manualCode.trim()
        if (!code) return
        setManualCode('')
        void handleScan(code)
    }

    // Bought item -> pre-queue in the Books tab (BatchScan reads this key on mount)
    const sendToBooks = (row: SourcingRow) => {
        if (!row.bookData) return
        const book = row.bookData as { title?: string; price?: number | string; stock_photo?: string; item_specifics?: { Author?: string } }
        try {
            const saved = localStorage.getItem('batchScanItems')
            const items: unknown[] = saved ? JSON.parse(saved) : []
            items.unshift({
                id: crypto.randomUUID(),
                isbn: row.gtin,
                title: book.title || row.title || row.gtin,
                author: book.item_specifics?.Author || '',
                condition: row.condition,
                price: book.price?.toString() || '',
                status: 'found',
                stock_photo: book.stock_photo,
                fullData: row.bookData,
            })
            localStorage.setItem('batchScanItems', JSON.stringify(items))
            updateRow(row.id, { sentToBooks: true })
            toast.success('Queued in Books tab — draft it when you\'re home')
        } catch {
            toast.error('Could not queue — Books list storage full?')
        }
    }

    const bought = history.filter(r => r.bought)
    const totalPaid = bought.reduce((s, r) => s + (parseFloat(r.paid || '') || 0), 0)
    const totalEstSold = bought.reduce((s, r) => s + (r.estSold || 0), 0)

    return (
        <div className="h-full overflow-auto p-4 md:p-6">
            <div className="mx-auto max-w-2xl space-y-4 pb-24">
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <h1 className="text-2xl font-display font-bold text-white tracking-tight">Source</h1>
                        <p className="text-slate-400 text-sm">Scan any barcode → buy/pass verdict from live eBay comps</p>
                    </div>
                    <Select value={condition} onValueChange={setCondition}>
                        <SelectTrigger className="w-[150px] h-9 text-xs shrink-0 bg-slate-900/60 border-white/10 text-white hover:bg-slate-800/80">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {CONDITION_OPTIONS.map(o => (
                                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                <CameraBarcodeScanner formats={SCAN_FORMATS} validate={isLikelyGtin} onDetect={handleScan} />

                <div className="flex gap-2">
                    <Input
                        value={manualCode}
                        onChange={e => setManualCode(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') checkManual() }}
                        placeholder="Type or wedge-scan a barcode…"
                        inputMode="numeric"
                        className="bg-slate-950/40 border-white/10 text-white placeholder-slate-500 focus-visible:ring-brand-500/50"
                    />
                    <Button onClick={checkManual} disabled={!manualCode.trim()} className="bg-brand-500 hover:bg-brand-600 text-white shadow-glow">
                        <Search size={15} className="mr-1.5" /> Check
                    </Button>
                </div>

                {loading && (
                    <div className="flex items-center justify-center gap-2 text-slate-300 bg-slate-900/40 backdrop-blur-2xl border border-white/5 shadow-glass rounded-3xl py-6">
                        <Loader2 className="h-5 w-5 animate-spin text-brand-400" /> Pulling comps…
                    </div>
                )}

                {current && !loading && <VerdictCard result={current} title={currentTitle} />}

                {/* Session history */}
                {history.length > 0 && (
                    <div className="bg-slate-900/40 backdrop-blur-2xl border border-white/5 shadow-glass rounded-3xl overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
                            <div className="text-sm font-medium text-slate-300">
                                {history.length} scanned · {bought.length} bought
                                {bought.length > 0 && (
                                    <span className="text-slate-500 font-normal">
                                        {' '}· spent {usd(totalPaid)} · est. resale {usd(totalEstSold)}
                                    </span>
                                )}
                            </div>
                            <Button variant="ghost" size="sm" className="h-7 text-xs text-slate-400 hover:text-rose-400"
                                onClick={() => { setHistory([]); setCurrent(null) }}>
                                <Trash2 size={13} className="mr-1" /> Clear
                            </Button>
                        </div>
                        <div className="divide-y divide-white/5">
                            {history.map(row => (
                                <div key={row.id} className="px-4 py-3 flex items-center gap-3">
                                    <Badge variant="outline" className={`shrink-0 text-[10px] ${VERDICT_STYLE[row.verdict].chip}`}>
                                        {VERDICT_STYLE[row.verdict].label}
                                    </Badge>
                                    <div className="flex-1 min-w-0">
                                        <div className="text-xs text-slate-200 truncate">{row.title || row.gtin}</div>
                                        <div className="text-[10px] text-slate-500">
                                            {row.maxBuy != null ? `pay ≤ ${usd(row.maxBuy)}` : row.gtin}
                                        </div>
                                    </div>
                                    {row.bought ? (
                                        <div className="flex items-center gap-1.5 shrink-0">
                                            <div className="relative w-16">
                                                <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-500">$</span>
                                                <Input
                                                    className="h-7 pl-4 text-xs bg-slate-950/40 border-white/10 text-white"
                                                    value={row.paid || ''}
                                                    onChange={e => updateRow(row.id, { paid: e.target.value })}
                                                    placeholder="paid"
                                                />
                                            </div>
                                            {row.bookData && !row.sentToBooks && (
                                                <Button variant="ghost" size="icon" className="h-7 w-7 hover:bg-white/5"
                                                    title="Queue in Books tab"
                                                    onClick={() => sendToBooks(row)}>
                                                    <BookOpen size={14} className="text-brand-400" />
                                                </Button>
                                            )}
                                            {row.sentToBooks && <BookOpen size={14} className="text-slate-600" />}
                                        </div>
                                    ) : (
                                        row.verdict !== 'PASS' && row.verdict !== 'NO_DATA' && (
                                            <Button variant="outline" size="sm" className="h-7 text-xs shrink-0 border-white/10 hover:bg-white/5"
                                                onClick={() => updateRow(row.id, { bought: true, paid: '' })}>
                                                Bought
                                            </Button>
                                        )
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
