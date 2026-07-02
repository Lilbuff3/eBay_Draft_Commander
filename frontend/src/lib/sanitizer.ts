/**
 * eBay 2026 Security Sanitizer
 * Handles strict requirements for:
 * 1. HTTPS-only links (HTTP is blocked)
 * 2. No Active Content (Scripts, IFrames, Forms)
 */

interface SanitizeResult {
    html: string
    changes: {
        httpUpgraded: number
        scriptsRemoved: number
        unsafeAttributesRemoved: number
    }
}

export function sanitizeDescription(html: string): SanitizeResult {
    let safeHtml = html
    const changes = {
        httpUpgraded: 0,
        scriptsRemoved: 0,
        unsafeAttributesRemoved: 0
    }

    // 1. Upgrade HTTP -> HTTPS
    // eBay 2026 Rule: All external links must be HTTPS
    const httpRegex = /http:\/\//g
    const httpMatches = safeHtml.match(httpRegex)
    if (httpMatches) {
        changes.httpUpgraded = httpMatches.length
        safeHtml = safeHtml.replace(httpRegex, 'https://')
    }

    // 2. Remove Script Tags (Regex approach for client-side simplicity)
    // Note: A full DOM parser is safer, but Regex is sufficient for standard 'script' blocks
    // Removing <script>...</script> content entirely
    const scriptRegex = /<script\b[^>]*>([\s\S]*?)<\/script>/gmi
    const scriptMatches = safeHtml.match(scriptRegex)
    if (scriptMatches) {
        changes.scriptsRemoved += scriptMatches.length
        safeHtml = safeHtml.replace(scriptRegex, '')
    }

    // 3. Remove <object>, <embed>, <iframe> (Active Content)
    const activeTags = ['iframe', 'object', 'embed', 'form', 'meta']
    activeTags.forEach(tag => {
        const regex = new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)<\\/${tag}>|<${tag}\\b[^>]*>`, 'gmi')
        const matches = safeHtml.match(regex)
        if (matches) {
            changes.scriptsRemoved += matches.length
            safeHtml = safeHtml.replace(regex, '')
        }
    })

    // 4. Remove href/src attributes carrying script-capable protocols entirely
    // (javascript:, vbscript:, data:). Stripping the whole attribute — not
    // swapping in href="#" — leaves no clickable stub behind.
    const jsProtocolRegex = /\s(href|src)\s*=\s*["']\s*(?:javascript|vbscript|data)\s*:[^"']*["']/gmi
    const jsMatches = safeHtml.match(jsProtocolRegex)
    if (jsMatches) {
        changes.unsafeAttributesRemoved += jsMatches.length
        safeHtml = safeHtml.replace(jsProtocolRegex, '')
    }

    // 5. Remove event handlers (onclick, onmouseover, etc.)
    const onEventRegex = /\s(on\w+)=["'][^"']*["']/gmi
    const onMatches = safeHtml.match(onEventRegex)
    if (onMatches) {
        changes.unsafeAttributesRemoved += onMatches.length
        safeHtml = safeHtml.replace(onEventRegex, '')
    }

    return {
        html: safeHtml,
        changes
    }
}
