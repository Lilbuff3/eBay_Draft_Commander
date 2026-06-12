// Resolves the price to pre-fill in the listing draft form.
// Priority: user-saved price > final pipeline price (market research
// cascade) > AI suggested price. Returns '' when none exists yet (job still
// processing) — the publish button is already disabled for empty/zero
// prices, and a fake default like 29.99 misleads the user into thinking
// pricing is done.
export function resolveDraftPrice(details: { user_price?: string | number | null; price?: string | number | null; suggested_price?: string | number | null }): string {
    for (const value of [details.user_price, details.price, details.suggested_price]) {
        const num = typeof value === 'string' ? parseFloat(value) : value
        if (typeof num === 'number' && isFinite(num) && num > 0) {
            return String(value)
        }
    }
    return ''
}
