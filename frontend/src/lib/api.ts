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

/** Thin wrapper around fetch that checks res.ok and throws on HTTP errors */
export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
    const res = await fetch(url, init)
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

export async function resumeQueue(): Promise<{ success: boolean; message?: string }> {
    return apiFetch(`${API_BASE}/resume`, { method: 'POST' })
}

export async function retryFailed(): Promise<{ success: boolean; retried?: number }> {
    return apiFetch(`${API_BASE}/retry`, { method: 'POST' })
}

export interface ClearResult {
    success: boolean
    count?: number
    folders_deleted?: number
    message?: string
}

export async function clearCompleted(deleteFolders = false): Promise<ClearResult> {
    return apiFetch(`${API_BASE}/clear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deleteFolders })
    })
}

export async function clearFailed(deleteFolders = false): Promise<ClearResult> {
    return apiFetch(`${API_BASE}/clear-failed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deleteFolders })
    })
}

export async function purgeStaleJobs(): Promise<{ success: boolean; count: number }> {
    return apiFetch(`${API_BASE}/purge-stale`, { method: 'POST' })
}

export async function deleteJob(jobId: string, deleteFolder = false): Promise<{ success: boolean }> {
    return apiFetch(`${API_BASE}/jobs/bulk-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobIds: [jobId], deleteFolders: deleteFolder })
    })
}

export async function bulkDeleteJobs(jobIds: string[], deleteFolders = false): Promise<{ success: boolean }> {
    return apiFetch(`${API_BASE}/jobs/bulk-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobIds, deleteFolders })
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

export async function addFolderToQueue(path: string): Promise<{ success: boolean; count: number; message: string }> {
    return apiFetch(`${API_BASE}/queue/add-folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
    })
}

export async function softRestart(): Promise<{ success: boolean; message: string }> {
    return apiFetch(`${API_BASE}/sys/restart`, { method: 'POST' })
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

export async function lookupBook(isbn: string): Promise<unknown> {
    return apiFetch(`${API_BASE}/lookup/book`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ isbn })
    })
}

export async function createJobFromMetadata(data: Record<string, unknown>): Promise<{ success: boolean; jobId?: string; error?: string }> {
    return apiFetch(`${API_BASE}/jobs/create-from-metadata`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
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
        comparables: Array<{ title: string; price: number }>
        price_source: string
        price_source_label?: string
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
    metadata?: { title?: string; condition?: string; category?: string }
): Promise<{ success: boolean; job_id?: string; jobId?: string; error?: string }> {
    const formData = new FormData()
    const fileArray = Array.from(files)
    fileArray.forEach(f => formData.append('files[]', f))

    if (metadata?.title) formData.append('title', metadata.title)
    if (metadata?.condition) formData.append('condition', metadata.condition)
    if (metadata?.category) formData.append('category', metadata.category)

    // Use XHR for upload progress tracking
    if (onProgress || metadata) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest()
            xhr.open('POST', `${API_BASE}/upload`)

            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable && onProgress) {
                    onProgress(e.loaded, e.total)
                }
            }

            xhr.onload = () => {
                try {
                    const result = JSON.parse(xhr.responseText)
                    if (xhr.status >= 200 && xhr.status < 300) {
                        if (result.job_id) toast.success('Upload started')
                        resolve(result)
                    } else {
                        toast.error(result.error || 'Upload failed')
                        reject(new Error(result.error || `Upload failed (${xhr.status})`))
                    }
                } catch {
                    toast.error('Upload failed')
                    reject(new Error('Invalid server response'))
                }
            }

            xhr.onerror = () => {
                toast.error('Upload failed')
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
        if (result.job_id) {
            toast.success('Upload started')
        }
        return result
    } catch (err) {
        toast.error('Upload failed')
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
}

export async function fetchAnalyticsSummary(days: string): Promise<SalesStats> {
    return apiFetch(`${API_BASE}/analytics/summary?days=${days}`)
}

export async function fetchRecentOrders(days: string, limit = 50): Promise<{ orders: Order[] }> {
    return apiFetch(`${API_BASE}/analytics/orders?days=${days}&limit=${limit}`)
}
