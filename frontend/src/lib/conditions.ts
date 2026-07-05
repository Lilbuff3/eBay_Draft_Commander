// eBay condition enum options shared across scan/detail UIs. Kept in lib/ so
// lazy-loaded pages (BatchScan, Sourcing) don't import each other just to reach it.
export const CONDITION_OPTIONS = [
    { value: 'NEW', label: 'New' },
    { value: 'NEW_OTHER', label: 'New - Open Box' },
    { value: 'LIKE_NEW', label: 'Like New' },
    { value: 'USED_EXCELLENT', label: 'Used - Excellent' },
    { value: 'USED_VERY_GOOD', label: 'Used - Very Good' },
    { value: 'USED_GOOD', label: 'Used - Good' },
    { value: 'USED_ACCEPTABLE', label: 'Used - Acceptable' },
] as const
