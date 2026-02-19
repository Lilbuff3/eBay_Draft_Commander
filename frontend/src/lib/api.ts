// API Types and Functions for eBay Draft Commander

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'paused' | 'skipped' | 'scheduled'

export interface Job {
    id: string
    name: string
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
    condition?: string | null
    scheduled_time?: string | null
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
async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
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

export async function clearCompleted(): Promise<{ success: boolean; message?: string }> {
    return apiFetch(`${API_BASE}/clear`, { method: 'POST' })
}

export interface CreateListingParams {
    jobId: string
    price?: string
    title?: string
    description?: string
    condition?: string
    fulfillmentPolicy?: string
    paymentPolicy?: string
    returnPolicy?: string
    processNow?: boolean
    scheduledTime?: string
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
        fulfillmentPolicy: params.fulfillmentPolicy,
        process_now: true,
        scheduled_time: params.scheduledTime
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
        market_price?: Record<string, unknown>
    }
    condition?: string | Record<string, unknown>
    condition_id?: number
    condition_description?: string
    analysis_mode?: string
    images: Array<{ name: string; path: string; url: string }>
    image_count: number
    raw_metadata: Record<string, unknown>
}

export async function fetchJobDetails(jobId: string): Promise<JobDetails> {
    return apiFetch(`${API_BASE}/job/${jobId}/details`)
}
