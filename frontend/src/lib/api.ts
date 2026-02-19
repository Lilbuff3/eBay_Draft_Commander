// API Types and Functions for eBay Draft Commander

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'scheduled'

export interface Job {
    id: string
    name: string
    status: JobStatus
    listing_id: string | null
    offer_id: string | null
    price: number | null
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
    current_job: { name: string; started: string } | null
    progress: {
        current: number
        total: number
        percent: number
    }
}

// API Functions
// Always use relative path — Flask serves both the SPA and API on the same origin
const API_BASE = '/api'

export async function fetchJobs(): Promise<Job[]> {
    const res = await fetch(`${API_BASE}/jobs`)
    return res.json()
}

export async function fetchStatus(): Promise<QueueStatus> {
    const res = await fetch(`${API_BASE}/status`)
    return res.json()
}


export async function fetchStats(): Promise<QueueStats> {
    // Helper to get stats from status if needed, or deprecate
    const status = await fetchStatus()
    return status.stats
}

export async function startQueue(): Promise<{ success: boolean; message?: string }> {
    const res = await fetch(`${API_BASE}/start`, { method: 'POST' })
    return res.json()
}

export async function pauseQueue(): Promise<{ success: boolean; message?: string }> {
    const res = await fetch(`${API_BASE}/pause`, { method: 'POST' })
    return res.json()
}

export async function resumeQueue(): Promise<{ success: boolean; message?: string }> {
    const res = await fetch(`${API_BASE}/resume`, { method: 'POST' })
    return res.json()
}

export async function retryFailed(): Promise<{ success: boolean; retried?: number }> {
    const res = await fetch(`${API_BASE}/retry`, { method: 'POST' })
    return res.json()
}

export async function clearCompleted(): Promise<{ success: boolean; message?: string }> {
    const res = await fetch(`${API_BASE}/clear`, { method: 'POST' })
    return res.json()
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
    // Use the job update endpoint to set metadata and trigger processing
    const payload = {
        title: params.title,
        price: params.price,
        description: params.description,
        condition: params.condition,
        fulfillmentPolicy: params.fulfillmentPolicy,
        process_now: true, // Always trigger if called via "Create Listing" button
        scheduled_time: params.scheduledTime
    }

    const res = await fetch(`${API_BASE}/job/${params.jobId}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    return res.json()
}

export async function scanInbox(): Promise<{ success: boolean; added: number; total: number; message: string }> {
    const res = await fetch(`${API_BASE}/scan`, { method: 'POST' })
    return res.json()
}

export async function addFolderToQueue(path: string): Promise<{ success: boolean; count: number; message: string }> {
    const res = await fetch(`${API_BASE}/queue/add-folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
    })
    return res.json()
}

export async function getSettings(): Promise<Record<string, string>> {
    const res = await fetch(`${API_BASE}/settings`)
    return res.json()
}

export async function saveSettings(settings: Record<string, string>): Promise<{ success: boolean; error?: string }> {
    const res = await fetch(`${API_BASE}/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
    })
    return res.json()
}

export async function lookupBook(isbn: string): Promise<unknown> {
    const res = await fetch(`${API_BASE}/lookup/book`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ isbn })
    })
    return res.json()
}

export async function createJobFromMetadata(data: Record<string, unknown>): Promise<{ success: boolean; jobId?: string; error?: string }> {
    const res = await fetch(`${API_BASE}/jobs/create-from-metadata`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    return res.json()
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
    item_specifics: Record<string, string>
    suggested_price?: number
    pricing_data: {
        confidence?: string
        comparables: Array<{ title: string; price: number }>
        price_source: string
    }
    condition?: string
    images: Array<{ name: string; path: string; url: string }>
    image_count: number
    raw_metadata: Record<string, unknown>
}

export async function fetchJobDetails(jobId: string): Promise<JobDetails> {
    const res = await fetch(`${API_BASE}/job/${jobId}/details`)
    return res.json()
}
