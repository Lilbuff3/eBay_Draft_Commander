import { describe, it, expect } from 'vitest'
import { normalizeIsbn, isLikelyIsbn, isLikelyGtin, ScanDeduper } from './isbn'

describe('normalizeIsbn', () => {
    it('strips hyphens and spaces', () => {
        expect(normalizeIsbn('978-0-201-61622-4')).toBe('9780201616224')
        expect(normalizeIsbn(' 0 201 61622 X ')).toBe('020161622X')
    })
    it('uppercases the ISBN-10 check digit', () => {
        expect(normalizeIsbn('020161622x')).toBe('020161622X')
    })
})

describe('isLikelyIsbn', () => {
    it('accepts ISBN-13 with 978/979 prefix', () => {
        expect(isLikelyIsbn('9780201616224')).toBe(true)
        expect(isLikelyIsbn('9791234567896')).toBe(true)
    })
    it('rejects 13 digits without bookland prefix', () => {
        expect(isLikelyIsbn('1234567890123')).toBe(false)
    })
    it('accepts ISBN-10 including X check digit', () => {
        expect(isLikelyIsbn('0201616224')).toBe(true)
        expect(isLikelyIsbn('020161622X')).toBe(true)
    })
    it('rejects short/garbage input', () => {
        expect(isLikelyIsbn('12345')).toBe(false)
        expect(isLikelyIsbn('notanisbn!')).toBe(false)
        expect(isLikelyIsbn('')).toBe(false)
    })
})

describe('isLikelyGtin', () => {
    it('accepts everything isLikelyIsbn accepts', () => {
        expect(isLikelyGtin('9780201616224')).toBe(true)
        expect(isLikelyGtin('020161622X')).toBe(true)
    })
    it('accepts UPC-A (12 digits)', () => {
        expect(isLikelyGtin('012345678905')).toBe(true)
    })
    it('accepts EAN-8', () => {
        expect(isLikelyGtin('96385074')).toBe(true)
    })
    it('accepts non-bookland EAN-13 (imports, media)', () => {
        expect(isLikelyGtin('4006381333931')).toBe(true)
    })
    it('rejects 11-digit junk and garbage', () => {
        expect(isLikelyGtin('12345678901')).toBe(false)
        expect(isLikelyGtin('notabarcode')).toBe(false)
        expect(isLikelyGtin('')).toBe(false)
    })
})

describe('ScanDeduper', () => {
    it('accepts first read, rejects repeat within window, accepts after', () => {
        const d = new ScanDeduper(3000)
        expect(d.shouldAccept('9780201616224', 1000)).toBe(true)
        expect(d.shouldAccept('9780201616224', 2500)).toBe(false)
        expect(d.shouldAccept('9780201616224', 6000)).toBe(true)
    })
    it('tracks codes independently', () => {
        const d = new ScanDeduper(3000)
        expect(d.shouldAccept('A', 1000)).toBe(true)
        expect(d.shouldAccept('B', 1001)).toBe(true)
        expect(d.shouldAccept('A', 1002)).toBe(false)
    })
    it('repeated rejected reads extend the window (held barcode)', () => {
        const d = new ScanDeduper(3000)
        expect(d.shouldAccept('A', 0)).toBe(true)
        expect(d.shouldAccept('A', 2900)).toBe(false)
        // window slides from the LAST read, so 5000 is still within 3s of 2900
        expect(d.shouldAccept('A', 5000)).toBe(false)
        expect(d.shouldAccept('A', 9000)).toBe(true)
    })
})
