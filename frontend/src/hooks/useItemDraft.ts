import { useState, useEffect, useRef, useCallback } from 'react'
import {
    createListing, fetchJobDetails, fetchJobImages,
    type Job, type JobDetails, type ItemDraft,
} from '@/lib/api'
import { resolveDraftPrice } from '@/lib/draftPrice'
import { mergeDraft } from '@/lib/mergeDraft'

// Factory, not a shared constant: itemSpecifics is an object and a shared
// reference could be mutated through the draft
const emptyDraft = (): ItemDraft => ({
    title: '',
    price: '',
    condition: '',
    shipping: null,
    scheduledTime: '',
    itemSpecifics: {},
    categoryId: '',
    categoryName: ''
})

/** Format a Date as a local-wall-time string for <input type="datetime-local"> */
function toLocalInputValue(date: Date): string {
    const offset = date.getTimezoneOffset() * 60000
    return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export interface UseItemDraftResult {
    draft: ItemDraft
    /** Merge updates into the draft, marking those fields as user-touched so
     * server refreshes (socket job_update → details refetch) can't overwrite them. */
    updateDraft: (updates: Partial<ItemDraft>) => void
    jobDetails: JobDetails | null
    isLoadingDetails: boolean
    jobImages: Array<{ name: string; url: string }>
    setJobImages: React.Dispatch<React.SetStateAction<Array<{ name: string; url: string }>>>
    isCreating: boolean
    createResult: { success: boolean; message: string } | null
    priceIsInvalid: boolean
    submitListing: () => Promise<void>
}

/**
 * Everything about editing one selected job's listing draft: details/images
 * fetching (with stale-response guards), the user-edit-protected draft merge,
 * and listing submission. Extracted from Dashboard.tsx so the page component
 * only wires layout.
 */
export function useItemDraft(selectedJob: Job | null): UseItemDraftResult {
    const [draft, setDraft] = useState<ItemDraft>(emptyDraft)
    const [jobDetails, setJobDetails] = useState<JobDetails | null>(null)
    const [isLoadingDetails, setIsLoadingDetails] = useState(false)
    const [jobImages, setJobImages] = useState<Array<{ name: string; url: string }>>([])
    const [isCreating, setIsCreating] = useState(false)
    const [createResult, setCreateResult] = useState<{ success: boolean; message: string } | null>(null)

    // Fields the user has edited for the currently selected job. Server
    // refreshes (socket job_update -> details refetch) must not overwrite them.
    const touchedFieldsRef = useRef<Set<string>>(new Set())
    const draftJobIdRef = useRef<string | null>(null)

    const updateDraft = useCallback((updates: Partial<ItemDraft>) => {
        Object.keys(updates).forEach(key => touchedFieldsRef.current.add(key))
        setDraft(prev => ({ ...prev, ...updates }))
    }, [])

    // Fetch all images when job is selected
    useEffect(() => {
        if (selectedJob) {
            // Guard against a slow response for job A landing after the user
            // has already switched to job B
            let stale = false
            setJobImages([])
            fetchJobImages(selectedJob.id)
                .then(data => {
                    if (stale) return
                    if (data.images && data.images.length > 0) {
                        setJobImages(data.images.map((img: { name: string; url?: string }) => ({
                            name: img.name,
                            url: img.url || `/api/job/${selectedJob.id}/image/${img.name}`
                        })))
                    }
                })
                .catch(err => console.error("Failed to load job images", err))
            return () => { stale = true }
        } else {
            setJobImages([])
        }
    }, [selectedJob])

    // Fetch job details when job is selected
    useEffect(() => {
        if (selectedJob) {
            if (draftJobIdRef.current !== selectedJob.id) {
                // Different job selected: discard edits and start clean
                draftJobIdRef.current = selectedJob.id
                touchedFieldsRef.current = new Set()
                setDraft(emptyDraft())
            }
            // Guard against a slow response for job A landing after the user
            // has already switched to job B (would clobber B's details/draft)
            let stale = false
            setIsLoadingDetails(true)
            setJobDetails(null)
            fetchJobDetails(selectedJob.id)
                .then(details => {
                    if (stale) return
                    if (!details.success) {
                        console.warn('fetchJobDetails returned success=false', details)
                        return
                    }
                    setJobDetails(details)
                    const newDraft: Partial<ItemDraft> = {
                        title: details.user_title || details.ai_title || selectedJob.name,
                        price: resolveDraftPrice(details),
                        condition: details.condition
                            ? (typeof details.condition === 'object' && details.condition !== null
                                ? String((details.condition as Record<string, unknown>).state ?? (details.condition as Record<string, unknown>).value ?? '')
                                : String(details.condition))
                            : '',
                        categoryId: details.category_id || '',
                        categoryName: details.category_name || ''
                    }

                    newDraft.scheduledTime = details.scheduled_time
                        ? toLocalInputValue(new Date(details.scheduled_time))
                        : toLocalInputValue(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000))
                    if (details.item_specifics) {
                        newDraft.itemSpecifics = { ...details.item_specifics }
                    }
                    // Merge instead of overwrite: job_update socket events
                    // re-run this effect while the user may be mid-edit
                    setDraft(prev => mergeDraft(newDraft, prev, touchedFieldsRef.current))
                })
                .catch(err => console.error("Failed to load job details", err))
                .finally(() => { if (!stale) setIsLoadingDetails(false) })
            return () => { stale = true }
        } else {
            setJobDetails(null)
            draftJobIdRef.current = null
            touchedFieldsRef.current = new Set()
            setDraft(emptyDraft())
        }
    }, [selectedJob])

    const priceIsInvalid = !draft.price || parseFloat(draft.price) <= 0

    const submitListing = useCallback(async () => {
        if (!selectedJob) return
        if (!draft.price || parseFloat(draft.price) <= 0) return
        setIsCreating(true)
        setCreateResult(null)

        try {
            const result = await createListing({
                jobId: selectedJob.id,
                price: draft.price,
                title: draft.title,
                condition: draft.condition || undefined,
                categoryId: draft.categoryId || undefined,
                categoryName: draft.categoryName || undefined,
                fulfillmentPolicy: draft.shipping || undefined,
                scheduledTime: draft.scheduledTime || undefined,
                itemSpecifics: draft.itemSpecifics,
                orderedImages: jobImages.map(img => img.name)
            })

            if (result.success) {
                setCreateResult({ success: true, message: result.message || 'Listing created!' })
            } else {
                setCreateResult({ success: false, message: result.error || 'Failed to create listing' })
            }
        } catch (e) {
            setCreateResult({ success: false, message: 'Error creating listing' })
            console.error(e)
        } finally {
            setIsCreating(false)
        }
    }, [selectedJob, draft, jobImages])

    return {
        draft, updateDraft,
        jobDetails, isLoadingDetails,
        jobImages, setJobImages,
        isCreating, createResult,
        priceIsInvalid,
        submitListing,
    }
}
