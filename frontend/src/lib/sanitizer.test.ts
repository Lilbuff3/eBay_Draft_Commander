import { describe, it, expect } from 'vitest'
import { sanitizeDescription } from './sanitizer'

describe('sanitizeDescription', () => {
    it('upgrades http:// links to https:// and counts each', () => {
        const { html, changes } = sanitizeDescription('<a href="http://a.com">x</a> http://b.com')
        expect(html).not.toContain('http://')
        expect(html).toContain('https://a.com')
        expect(changes.httpUpgraded).toBe(2)
    })

    it('strips <script> blocks entirely', () => {
        const { html, changes } = sanitizeDescription('hi<script>alert(1)</script>bye')
        expect(html).toBe('hibye')
        expect(changes.scriptsRemoved).toBeGreaterThanOrEqual(1)
    })

    it('removes iframe/object/embed/form active content', () => {
        const { html } = sanitizeDescription('<iframe src="x"></iframe><form>z</form>ok')
        expect(html).toContain('ok')
        expect(html).not.toContain('<iframe')
        expect(html).not.toContain('<form')
    })

    it('strips javascript: protocol hrefs entirely — no clickable stub left', () => {
        const { html, changes } = sanitizeDescription('<a href="javascript:alert(1)">x</a>')
        expect(html).not.toContain('javascript:')
        expect(html).not.toContain('href')
        expect(changes.unsafeAttributesRemoved).toBe(1)
    })

    it('strips case and whitespace variants of script protocols', () => {
        const { html } = sanitizeDescription('<a href=" JavaScript:alert(1)">x</a><img src="VBScript:evil()">')
        expect(html.toLowerCase()).not.toContain('javascript:')
        expect(html.toLowerCase()).not.toContain('vbscript:')
    })

    it('strips data: URIs in href/src', () => {
        const { html } = sanitizeDescription('<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>')
        expect(html).not.toContain('data:')
    })

    it('strips inline event handlers', () => {
        const { html, changes } = sanitizeDescription('<div onclick="evil()">x</div>')
        expect(html).not.toContain('onclick')
        expect(changes.unsafeAttributesRemoved).toBe(1)
    })

    it('leaves clean html untouched and reports zero changes', () => {
        const clean = '<p style="color:red">Hello <b>world</b></p>'
        const { html, changes } = sanitizeDescription(clean)
        expect(html).toBe(clean)
        expect(changes).toEqual({ httpUpgraded: 0, scriptsRemoved: 0, unsafeAttributesRemoved: 0 })
    })
})
