import { describe, it, expect } from 'vitest'
import { estimateNet } from './fees'

describe('estimateNet', () => {
    it('subtracts FVF, processing fee and shipping', () => {
        // 100 - (13.25 + 0.30) - 6.50
        expect(estimateNet(100)).toBeCloseTo(79.95, 2)
    })

    it('returns 0 for a missing or zero price', () => {
        expect(estimateNet(0)).toBe(0)
        expect(estimateNet(-5)).toBe(0)
    })

    it('goes negative when the fees exceed a tiny price', () => {
        expect(estimateNet(5)).toBeLessThan(0)
    })
})
