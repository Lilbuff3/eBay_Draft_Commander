import { describe, it, expect } from 'vitest'
import { mergeDraft } from './mergeDraft'
import type { ItemDraft } from './api'

const base: ItemDraft = {
    title: '',
    price: '',
    description: '',
    condition: '',
    shipping: null,
    scheduledTime: '',
    itemSpecifics: {},
    categoryId: '',
    categoryName: ''
}

describe('mergeDraft', () => {
    it('fills untouched fields from server values', () => {
        const out = mergeDraft(
            { title: 'Nike Romaleos 4', price: '104.99' },
            base,
            new Set()
        )
        expect(out.title).toBe('Nike Romaleos 4')
        expect(out.price).toBe('104.99')
    })

    it('never overwrites a field the user touched', () => {
        const current = { ...base, price: '120', title: 'My custom title' }
        const out = mergeDraft(
            { title: 'Nike Romaleos 4', price: '104.99', condition: 'USED_EXCELLENT' },
            current,
            new Set(['price', 'title'])
        )
        expect(out.price).toBe('120')
        expect(out.title).toBe('My custom title')
        expect(out.condition).toBe('USED_EXCELLENT')
    })

    it('keeps current value when server omits a field', () => {
        const current = { ...base, condition: 'USED_GOOD' }
        const out = mergeDraft({ title: 'X' }, current, new Set())
        expect(out.condition).toBe('USED_GOOD')
    })

    it('treats itemSpecifics as a single touched unit', () => {
        const current = { ...base, itemSpecifics: { Brand: 'Nike', Size: '9.5' } }
        const out = mergeDraft(
            { itemSpecifics: { Brand: 'Adidas' } },
            current,
            new Set(['itemSpecifics'])
        )
        expect(out.itemSpecifics).toEqual({ Brand: 'Nike', Size: '9.5' })
    })

    it('does not blank out fields when server value is empty string', () => {
        const current = { ...base, title: 'Already set' }
        const out = mergeDraft({ title: '' }, current, new Set())
        expect(out.title).toBe('Already set')
    })
})
