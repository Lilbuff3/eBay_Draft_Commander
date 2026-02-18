// API client — thin fetch wrappers over the Flask backend.
// All paths are relative so they work in any environment via the Vite proxy.

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type JobStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'paused'
  | 'skipped'

export interface Job {
  id: string
  folder_path: string
  folder_name: string
  status: JobStatus
  listing_id: string | null
  offer_id: string | null
  price: string | null
  user_title: string | null
  user_price: string | null
  user_description: string | null
  user_condition: string | null
  ai_data: Record<string, unknown>
  item_specifics: Record<string, unknown>
  error_type: string | null
  error_message: string | null
  attempts: number
  max_attempts: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  timing: Record<string, unknown>
  job_metadata: Record<string, unknown>
}

// JobDetails is the same shape as Job — aliased for callsite clarity.
export type JobDetails = Job

export interface QueueStats {
  total: number
  pending: number
  processing: number
  completed: number
  failed: number
  skipped: number
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText)
    throw new Error(`API error ${response.status}: ${text}`)
  }

  return response.json() as Promise<T>
}

function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' })
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
}

// ---------------------------------------------------------------------------
// Queue
// ---------------------------------------------------------------------------

export async function fetchStatus(): Promise<{ queue: Job[]; stats: QueueStats }> {
  return get('/api/queue/status')
}

export async function fetchJobs(): Promise<{ jobs: Job[] }> {
  return get('/api/queue/jobs')
}

export async function startQueue(): Promise<{ success: boolean }> {
  return post('/api/queue/start')
}

export async function pauseQueue(): Promise<{ success: boolean }> {
  return post('/api/queue/pause')
}

export async function fetchJobDetails(jobId: string): Promise<JobDetails> {
  return get(`/api/queue/job/${jobId}`)
}

export async function addFolderToQueue(
  folderPath: string,
): Promise<{ success: boolean; job: Job }> {
  return post('/api/queue/add-folder', { folder_path: folderPath })
}

// ---------------------------------------------------------------------------
// Inbox
// ---------------------------------------------------------------------------

export async function scanInbox(): Promise<{
  success: boolean
  added: number
  total: number
}> {
  return post('/api/inbox/scan')
}

// ---------------------------------------------------------------------------
// Listing
// ---------------------------------------------------------------------------

export async function createListing(
  files: File[],
  itemName: string,
  price: string,
  description: string,
): Promise<{ success: boolean; listing_id?: string }> {
  const form = new FormData()
  files.forEach((file) => form.append('files', file))
  form.append('itemName', itemName)
  form.append('price', price)
  form.append('description', description)

  // FormData requests must NOT set Content-Type — the browser sets it with the boundary.
  const response = await fetch('/api/listing/create-from-photos', {
    method: 'POST',
    body: form,
  })

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText)
    throw new Error(`API error ${response.status}: ${text}`)
  }

  return response.json()
}

// ---------------------------------------------------------------------------
// Book lookup / metadata
// ---------------------------------------------------------------------------

export async function lookupBook(isbn: string): Promise<Record<string, unknown>> {
  return get(`/api/lookup/book?isbn=${encodeURIComponent(isbn)}`)
}

export async function createJobFromMetadata(
  metadata: Record<string, unknown>,
): Promise<{ success: boolean; job: Job }> {
  return post('/api/jobs/create-from-metadata', metadata)
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export async function getSettings(): Promise<Record<string, unknown>> {
  return get('/api/settings')
}

export async function saveSettings(
  settings: Record<string, unknown>,
): Promise<{ success: boolean }> {
  return post('/api/settings', settings)
}
