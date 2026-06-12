import { describe, it, expect } from 'vitest'
import { resolveDraftPrice } from './draftPrice'

describe('resolveDraftPrice', () => {
    it('prefers the final cascade price over the AI suggested price', () => {
        expect(resolveDraftPrice({ price: '104.99', suggested_price: 95 })).toBe('104.99')
    })

    it('prefers a user-saved price over everything', () => {
        expect(resolveDraftPrice({ user_price: '120', price: '104.99', suggested_price: 95 })).toBe('120')
    })

    it('falls back to suggested_price when no final price yet', () => {
        expect(resolveDraftPrice({ price: null, suggested_price: 95 })).toBe('95')
    })

    it('returns empty string while pricing is in progress — never a fake default', () => {
        expect(resolveDraftPrice({ price: null, suggested_price: null })).toBe('')
        expect(resolveDraftPrice({})).toBe('')
    })

    it('ignores zero and non-numeric prices', () => {
        expect(resolveDraftPrice({ price: '0', suggested_price: 95 })).toBe('95')
        expect(resolveDraftPrice({ price: 'N/A', suggested_price: null })).toBe('')
        expect(resolveDraftPrice({ price: 0, suggested_price: 0 })).toBe('')
    })

    it('accepts numeric price values', () => {
        expect(resolveDraftPrice({ price: 104.99 })).toBe('104.99')
    })
})
