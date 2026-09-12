/**
 * Selling-cost rates, mirrored from backend/app/core/selling_costs.py.
 *
 * /api/jobs carries no fee breakdown, so the capture sheet's session estimate
 * computes its own. These must match selling_costs.fees() and its
 * DEFAULT_SHIP_COST, or the scoreboard disagrees with the Profit tab — which
 * is exactly what happened while this file claimed to mirror
 * SOURCING_SHIP_COST ($5.00) but carried $6.50.
 *
 * ponytail: hand-mirrored constants. If they drift again, serve them from the
 * backend instead of copying: the scoreboard is a rough forward estimate, not
 * worth an endpoint until it's wrong twice.
 */
export const EBAY_FINAL_VALUE_FEE_RATE = 0.1325
export const EBAY_PAYMENT_PROCESSING_FEE = 0.30
export const DEFAULT_SHIP_COST = 5.0

/** Net proceeds on a list price, before COGS. Not a sale — list price is a guess. */
export function estimateNet(listPrice: number): number {
    if (listPrice <= 0) return 0
    return listPrice - (listPrice * EBAY_FINAL_VALUE_FEE_RATE + EBAY_PAYMENT_PROCESSING_FEE) - DEFAULT_SHIP_COST
}
