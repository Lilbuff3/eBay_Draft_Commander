// API Types and Functions for eBay Draft Commander
import { toast } from 'sonner'

export type JobStatus = 'pending' | 'processing' | 'awaiting_condition' | 'completed' | 'failed' | 'paused' | 'skipped' | 'scheduled' | 'needs_review' | 'pending_review'

export interface Job {
    id: string
    name: string
    display_name?: string
    status: JobStatus
    folder_path: string
    listing_id: string | null
    offer_id: string | null
    price: string | null
    error_type: string | null
    error_message: string | null
    started_at: string | null
    completed_at: string | null
    thumbnail_url?: string | null
    thumbnail_name?: string | null
    condition?: string | null
    scheduled_time?: string | null
    confidence_score?: number | null
    ai_data?: Record<string, unknown> | null
}

export interface QueueStats {
    pending: number
    completed: number
    failed: number
    total: number
}

export interface QueueStatus {
    status: 'idle' | 'ready' | 'processing' | 'paused'
    stats: QueueStats
    current_job: { id: string; name: string; status: string } | null
    progress: {
        current: number
        total: number
        percent: number
    }
}

// API Functions
// Always use relative path — Flask serves both the SPA and API on the same origin
const API_BASE = '/api'

// Remote (non-loopback) access requires an API key that matches the
// API_ACCESS_TOKEN configured in Settings on the server machine.
const API_KEY_STORAGE = 'dc-api-key'

export function getApiKey(): string | null {
    try {
        return localStorage.getItem(API_KEY_STORAGE)
    } catch {
        return null
    }
}

function storeApiKey(key: string) {
    try {
        localStorage.setItem(API_KEY_STORAGE, key)
    } catch {
        // Private browsing — key just won't persist across reloads
    }
}

function withApiKey(init?: RequestInit): RequestInit {
    const key = getApiKey()
    if (!key) return init ?? {}
    const headers = new Headers(init?.headers)
    headers.set('X-API-Key', key)
    return { ...init, headers }
}

/** Drop-in fetch that attaches the API key header. For call sites that need
 * the raw Response; prefer apiFetch<T>() for JSON endpoints. */
export function fetchWithKey(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    return fetch(input, withApiKey(init))
}

// --- 401 recovery: one in-app dialog shared by every concurrent request ---
// The ApiKeyDialog component (mounted in App) registers a handler; the first
// 401 opens it and every other 401 awaits the same promise, so a cold load
// firing five requests shows one dialog, not five stacked prompts.
type KeyRequestHandler = () => Promise<string | null>
let keyRequestHandler: KeyRequestHandler | null = null
let pendingKeyRequest: Promise<string | null> | null = null

export function setApiKeyRequestHandler(handler: KeyRequestHandler | null) {
    keyRequestHandler = handler
}

function requestApiKey(): Promise<string | null> {
    if (!keyRequestHandler) return Promise.resolve(null)
    if (!pendingKeyRequest) {
        pendingKeyRequest = keyRequestHandler().finally(() => { pendingKeyRequest = null })
    }
    return pendingKeyRequest
}

// Per-request timeout so a hung connection (phone asleep, Tailscale
// re-handshake, backend restart gap) fails fast instead of hanging forever.
const REQUEST_TIMEOUT_MS = 15000
const RETRY_DELAY_MS = 800

function isIdempotent(init?: RequestInit): boolean {
    const method = (init?.method ?? 'GET').toUpperCase()
    return method === 'GET' || method === 'HEAD'
}

/** fetch + API key + an AbortController timeout. Respects a caller-supplied
 * signal (aborting theirs aborts ours). */
async function fetchWithTimeout(url: string, init?: RequestInit): Promise<Response> {
    const merged = withApiKey(init)
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
    const external = merged.signal
    if (external) {
        if (external.aborted) controller.abort()
        else external.addEventListener('abort', () => controller.abort(), { once: true })
    }
    try {
        return await fetch(url, { ...merged, signal: controller.signal })
    } finally {
        clearTimeout(timer)
    }
}

/** Thin wrapper around fetch that checks res.ok and throws on HTTP errors */
export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
    let res: Response
    try {
        res = await fetchWithTimeout(url, init)
    } catch (err) {
        // Network error or timeout. Retry ONCE for idempotent GETs — covers a
        // transient blip (phone unlock, Tailscale re-handshake, ~3s restart gap).
        // Never auto-retry writes (the SW background-syncs those), and don't
        // retry if the caller deliberately aborted.
        if (isIdempotent(init) && !init?.signal?.aborted) {
            await new Promise(r => setTimeout(r, RETRY_DELAY_MS))
            res = await fetchWithTimeout(url, init)
        } else {
            throw err
        }
    }
    if (res.status === 401) {
        const entered = await requestApiKey()
        if (entered?.trim()) {
            storeApiKey(entered.trim())
            res = await fetchWithTimeout(url, init)
        }
    }
    if (!res.ok) {
        const body = await res.text().catch(() => '')
        throw new Error(`API ${init?.method ?? 'GET'} ${url} failed (${res.status}): ${body}`)
    }
    return res.json()
}

export async function fetchJobs(): Promise<Job[]> {
    return apiFetch(`${API_BASE}/jobs`)
}

export async function fetchPendingListings(): Promise<Job[]> {
    const res = await apiFetch<{ listings: Job[] }>(`${API_BASE}/listings/pending`)
    return res.listings
}

export async function quickEditListing(jobId: string, updates: { title?: string; price?: string; condition?: string }): Promise<{ success: boolean }> {
    return apiFetch(`${API_BASE}/listings/${jobId}/quick-edit`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
    })
}

export async function approvePendingListings(listingIds: string[]): Promise<{ success: boolean; approved_count: number }> {
    return apiFetch(`${API_BASE}/listings/batch-approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ listing_ids: listingIds })
    })
}

export async function fetchStatus(): Promise<QueueStatus> {
    return apiFetch(`${API_BASE}/status`)
}

export async function fetchStats(): Promise<QueueStats> {
    const status = await fetchStatus()
    return status.stats
}

export async function startQueue(): Promise<{ success: boolean; message?: string }> {
    return apiFetch(`${API_BASE}/start`, { method: 'POST' })
}

export async function pauseQueue(): Promise<{ success: boolean; message?: string }> {
    return apiFetch(`${API_BASE}/pause`, { method: 'POST' })
}

export async function deleteJob(jobId: string, deleteFolder = false): Promise<{ success: boolean }> {
    return apiFetch(`${API_BASE}/jobs/bulk-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobIds: [jobId], deleteFolders: deleteFolder })
    })
}

export interface CreateFromMetadataPayload {
    title: string
    isbn?: string
    description?: string
    thumbnail?: string
    condition?: string
    price?: string
    category_id?: string
    item_specifics?: Record<string, unknown>
    pricing_data?: Record<string, unknown>
    user_approved?: boolean
    cogs?: number
    source: string
}

export interface CreateFromMetadataResult {
    success: boolean
    jobId?: string
    cover?: boolean
    error?: string
}

/** Create a job from metadata (book batch scan). Optional real photo rides
 * along as multipart so the queue can never grab the job before it lands. */
export async function createJobFromMetadata(
    payload: CreateFromMetadataPayload,
    photo?: File
): Promise<CreateFromMetadataResult> {
    if (photo) {
        const form = new FormData()
        form.append('payload', JSON.stringify(payload))
        form.append('photo', photo)
        return apiFetch(`${API_BASE}/jobs/create-from-metadata`, { method: 'POST', body: form })
    }
    return apiFetch(`${API_BASE}/jobs/create-from-metadata`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
}

export async function fetchJobImages(jobId: string): Promise<{ images: Array<{ name: string; url: string }> }> {
    return apiFetch(`${API_BASE}/job/${jobId}/images`)
}

export interface CreateListingParams {
    jobId: string
    price?: string
    title?: string
    description?: string
    condition?: string
    categoryId?: string
    categoryName?: string
    fulfillmentPolicy?: string
    paymentPolicy?: string
    returnPolicy?: string
    processNow?: boolean
    scheduledTime?: string
    itemSpecifics?: Record<string, string>
    orderedImages?: string[]
}

export interface ItemDraft {
    title: string;
    price: string;
    /** listing description (HTML source); seeded from user_description || ai_description */
    description: string;
    condition: string;
    shipping: string | null;
    scheduledTime: string;
    itemSpecifics: Record<string, string>;
    categoryId: string;
    categoryName: string;
}

export interface CreateListingResult {
    success: boolean
    message?: string
    error?: string
}

export async function createListing(params: CreateListingParams): Promise<CreateListingResult> {
    const payload = {
        title: params.title,
        price: params.price,
        description: params.description,
        condition: params.condition,
        category_id: params.categoryId,
        category_name: params.categoryName,
        fulfillmentPolicy: params.fulfillmentPolicy,
        item_specifics: params.itemSpecifics,
        process_now: true,
        scheduled_time: params.scheduledTime,
        ordered_images: params.orderedImages
    }
    return apiFetch(`${API_BASE}/job/${params.jobId}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
}

export async function scanInbox(): Promise<{ success: boolean; added: number; total: number; message: string }> {
    return apiFetch(`${API_BASE}/scan`, { method: 'POST' })
}

export async function softRestart(): Promise<{ success: boolean; message: string }> {
    return apiFetch(`${API_BASE}/system/restart`, { method: 'POST' })
}

export async function getSettings(): Promise<Record<string, string>> {
    return apiFetch(`${API_BASE}/settings`)
}

export async function saveSettings(settings: Record<string, string>): Promise<{ success: boolean; error?: string }> {
    return apiFetch(`${API_BASE}/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
    })
}


/** One market comparable from the pricing engine (Browse API = active asking prices) */
export interface PricingComp {
    title: string
    price: number
    condition?: string
    url?: string
    image_url?: string
    end_date?: string
}

export interface JobDetails {
    success: boolean
    id: string
    name: string
    status: JobStatus
    folder_path: string
    ai_title: string
    ai_description: string
    user_title?: string
    user_price?: string
    user_description?: string
    price?: string | null
    scheduled_time?: string | null
    category_id?: string
    category_name?: string
    category_keywords?: string[]
    item_specifics: Record<string, string>
    identification?: Record<string, unknown>
    suggested_price?: number
    price_reasoning?: string
    pricing_data: {
        confidence?: string
        comps?: PricingComp[]
        median_price?: number | null
        price_range?: [number, number] | null
        comp_count?: number | null
        reasoning?: string
        pricing_confidence?: 'high' | 'medium' | 'low' | 'user' | null
        pricing_confidence_reason?: string | null
        price_source: string
        price_source_label?: string
        source?: string
        market_price?: Record<string, unknown>
    }
    profit_breakdown?: {
        listing_price: number
        ebay_fee: number
        ebay_fee_rate: number
        payment_fee: number
        shipping_cost: number
        shipping_method: string
        take_home: number
    }
    condition?: string | Record<string, unknown>
    condition_id?: number
    condition_description?: string
    analysis_mode?: string
    ebay_aspect_schema?: Array<{ name: string; values: string[]; isRequired?: boolean }>
    images: Array<{ name: string; path: string; url: string }>
    image_count: number
    raw_metadata: Record<string, unknown>
}

export async function fetchJobDetails(jobId: string): Promise<JobDetails> {
    return apiFetch(`${API_BASE}/job/${jobId}/details`)
}

export async function fetchCategoryAspects(categoryId: string): Promise<Array<{ name: string; values: string[]; isRequired?: boolean }>> {
    return apiFetch(`${API_BASE}/lookup/category/${categoryId}/aspects`)
}

export interface CategorySuggestion {
    category_id: string
    category_name: string
    full_path: string
}

export async function searchCategories(query: string): Promise<CategorySuggestion[]> {
    return apiFetch(`${API_BASE}/lookup/category?q=${encodeURIComponent(query)}`)
}

export async function uploadFiles(
    files: FileList | File[],
    onProgress?: (loaded: number, total: number) => void,
    metadata?: { title?: string; condition?: string; category?: string; cogs?: number },
    // silent: caller owns success/error feedback (mobile capture sheet shows its
    // own interstitial + retry toast — api-level toasts would double up)
    opts?: { silent?: boolean }
): Promise<{ success: boolean; job_id?: string; jobId?: string; error?: string }> {
    const silent = opts?.silent ?? false
    const formData = new FormData()
    const fileArray = Array.from(files)
    fileArray.forEach(f => formData.append('files[]', f))

    if (metadata?.title) formData.append('title', metadata.title)
    if (metadata?.condition) formData.append('condition', metadata.condition)
    if (metadata?.category) formData.append('category', metadata.category)
    if (metadata?.cogs !== undefined) formData.append('cogs', metadata.cogs.toString())

    // Use XHR for upload progress tracking
    if (onProgress || metadata) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest()
            xhr.open('POST', `${API_BASE}/upload`)
            const apiKey = getApiKey()
            if (apiKey) xhr.setRequestHeader('X-API-Key', apiKey)

            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable && onProgress) {
                    onProgress(e.loaded, e.total)
                }
            }

            xhr.onload = () => {
                try {
                    const result = JSON.parse(xhr.responseText)
                    if (xhr.status >= 200 && xhr.status < 300) {
                        if (result.job_id && !silent) toast.success('Upload started')
                        resolve(result)
                    } else {
                        if (!silent) toast.error(result.error || 'Upload failed')
                        reject(new Error(result.error || `Upload failed (${xhr.status})`))
                    }
                } catch {
                    if (!silent) toast.error('Upload failed')
                    reject(new Error('Invalid server response'))
                }
            }

            xhr.onerror = () => {
                if (!silent) toast.error('Upload failed')
                reject(new Error('Network error'))
            }

            xhr.send(formData)
        })
    }

    // Fallback: standard fetch (no progress)
    try {
        const result = await apiFetch<{ success: boolean; job_id?: string; error?: string }>(
            `${API_BASE}/upload`,
            { method: 'POST', body: formData }
        )
        if (result.job_id && !silent) {
            toast.success('Upload started')
        }
        return result
    } catch (err) {
        if (!silent) toast.error('Upload failed')
        throw err
    }
}

// --- Analytics ---

export interface SalesStats {
    total_revenue: number
    orders_count: number
    items_sold: number
    average_order_value: number
    chart_data: { date: string; sales: number }[]
    best_sellers: { title: string; qty: number; revenue: number }[]
    active_listings_count?: number
    sell_through_rate?: number
}

export interface Order {
    orderId: string
    creationDate: string
    buyer: string
    total: number
    status: string
    itemCount: number
    itemTitle?: string | null
    legacyItemId?: string | null
    quantity?: number | null
    shipByDate?: string | null
    paidDate?: string | null
    thumbnailUrl?: string | null
}

export async function fetchAnalyticsSummary(days: string): Promise<SalesStats> {
    return apiFetch(`${API_BASE}/analytics/summary?days=${days}`)
}

export async function fetchRecentOrders(days: string, limit = 50): Promise<{ orders: Order[] }> {
    return apiFetch(`${API_BASE}/analytics/orders?days=${days}&limit=${limit}`)
}

export async function fetchOrders(days = '90', limit = 100): Promise<{ orders: Order[] }> {
    return apiFetch(`${API_BASE}/orders?days=${days}&limit=${limit}`)
}

export async function trackEvent(event: string, data: Record<string, unknown> = {}): Promise<void> {
    try {
        // fetchWithKey so Tailscale/phone sessions (API_ACCESS_TOKEN) still log
        await fetchWithKey(`${API_BASE}/analytics/track`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ event, data }),
        })
    } catch {
        // Silently swallow analytics errors so they never interrupt UX
    }
}
