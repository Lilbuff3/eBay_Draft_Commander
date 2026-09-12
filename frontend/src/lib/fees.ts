/**
 * Selling-cost rates, mirrored from backend/app/core/constants.py.
 *
 * The backend is the source of truth — /api/jobs does not carry a fee
 * breakdown, so session-level estimates in the capture sheet need them here.
 * Keep in sync with EBAY_FINAL_VALUE_FEE_RATE, EBAY_PAYMENT_PROCESSING_FEE
 * and SOURCING_SHIP_COST.
 */
export const EBAY_FINAL_VALUE_FEE_RATE = 0.1325
export const EBAY_PAYMENT_PROCESSING_FEE = 0.30
export const DEFAULT_SHIP_COST = 6.5

/** Net proceeds on a list price, before COGS. Not a sale — list price is a guess. */
export function estimateNet(listPrice: number): number {
    if (listPrice <= 0) return 0
    return listPrice - (listPrice * EBAY_FINAL_VALUE_FEE_RATE + EBAY_PAYMENT_PROCESSING_FEE) - DEFAULT_SHIP_COST
}
