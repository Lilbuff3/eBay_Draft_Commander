import { Shirt, Footprints, Cpu, BookOpen, Package, type LucideIcon } from 'lucide-react'

/**
 * Category-first capture: the four things this seller lists. Tapping a card opens
 * only a category-tuned condition picker, then photos -> submit. The chosen
 * `condition` value is an eBay condition enum (mapped to a category-correct ID
 * downstream via CONDITION_ID_MAP + the category-aware layer); `id` is sent as a
 * soft category hint for the pipeline.
 */
export interface ConditionPreset {
    label: string
    /** eBay condition enum (see backend CONDITION_MAP / CONDITION_ID_MAP) */
    value: string
}

export interface CaptureCategory {
    id: string
    label: string
    icon: LucideIcon
    /** card icon tint (text + bg classes) */
    iconText: string
    iconBg: string
    conditions: ConditionPreset[]
}

// Apparel (clothing + shoes) share eBay's apparel condition set.
const APPAREL: ConditionPreset[] = [
    { label: 'New with tags', value: 'NEW' },
    { label: 'New without tags', value: 'NEW_OTHER' },
    { label: 'New with defects', value: 'NEW_WITH_DEFECTS' },
    { label: 'Pre-owned', value: 'USED_EXCELLENT' },
]

// Catch-all set for anything outside the four verticals. Also the capture
// sheet's fallback when no category was picked.
export const GENERIC_CONDITIONS: ConditionPreset[] = [
    { label: 'New', value: 'NEW' },
    { label: 'Like New', value: 'LIKE_NEW' },
    { label: 'Good', value: 'USED_GOOD' },
    { label: 'Acceptable', value: 'USED_ACCEPTABLE' },
    { label: 'For Parts', value: 'FOR_PARTS_OR_NOT_WORKING' },
]

export const CAPTURE_CATEGORIES: CaptureCategory[] = [
    {
        id: 'clothing', label: 'Clothing', icon: Shirt,
        iconText: 'text-persimmon-600', iconBg: 'bg-persimmon-100',
        conditions: APPAREL,
    },
    {
        id: 'shoes', label: 'Shoes', icon: Footprints,
        iconText: 'text-sage-700', iconBg: 'bg-sage-100',
        conditions: APPAREL,
    },
    {
        id: 'electronics', label: 'Electronics', icon: Cpu,
        iconText: 'text-blue-700', iconBg: 'bg-blue-100',
        conditions: [
            { label: 'New', value: 'NEW' },
            { label: 'Open box', value: 'NEW_OTHER' },
            { label: 'Used – works', value: 'USED_EXCELLENT' },
            { label: 'For parts', value: 'FOR_PARTS_OR_NOT_WORKING' },
        ],
    },
    {
        id: 'books', label: 'Books & Media', icon: BookOpen,
        iconText: 'text-amber-700', iconBg: 'bg-amber-100',
        conditions: [
            { label: 'Brand new', value: 'NEW' },
            { label: 'Like new', value: 'LIKE_NEW' },
            { label: 'Very good', value: 'USED_VERY_GOOD' },
            { label: 'Good', value: 'USED_GOOD' },
            { label: 'Acceptable', value: 'USED_ACCEPTABLE' },
        ],
    },
    // Escape hatch: the picker is the only front door on mobile, so anything
    // outside the four verticals needs a card too. AI decides the real category.
    {
        id: 'other', label: 'Something else', icon: Package,
        iconText: 'text-stone-600', iconBg: 'bg-stone-100',
        conditions: GENERIC_CONDITIONS,
    },
]

export function getCaptureCategory(id?: string | null): CaptureCategory | undefined {
    if (!id) return undefined
    return CAPTURE_CATEGORIES.find(c => c.id === id)
}
