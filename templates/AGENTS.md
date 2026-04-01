<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# templates

## Purpose
eBay listing description HTML templates used during listing creation. Contains HTML structure with inline styles and template variables (`{{TITLE}}`, `{{DESCRIPTION}}`, `{{ASPECTS}}`, etc.) that are interpolated at rendering time by TemplateManager.

## Key Files
| File | Description |
|------|-------------|
| `ebay_master.html` | Main eBay listing description template: title section, images, item specifics table, product description, shipping & returns sections. Mobile-optimized with inline styles only (eBay strips `<style>` tags on mobile). ~1.8KB. |

## Subdirectories
(None — all templates in root of templates/ directory)

## For AI Agents

### Working In This Directory
- Edit `ebay_master.html` to change listing description layout, sections, or visual styling
- **CRITICAL: Use inline styles only** — eBay strips `<head>`, `<style>`, and `<link>` tags on mobile devices
- Template variables (replaced at render time):
  - `{{TITLE}}` — product title
  - `{{IMAGES}}` — image gallery HTML
  - `{{ASPECTS}}` — item specifics table (key-value pairs)
  - `{{DESCRIPTION}}` — product description with research data injected
  - `{{CONDITION}}` — item condition (New, Like New, etc.)
- Template variables are replaced by `TemplateManager.render_template()` in `backend/app/services/template_manager.py`
- Research data (specs, pricing comps) injected into `{{DESCRIPTION}}` via `{research_specs_section}` placeholder
- All user-provided content in variables is HTML-escaped via `html.escape()` to prevent XSS attacks

### HTML Structure
- Use `<table>` for item specifics (eBay-friendly, responsive)
- Use `<br>` for line breaks (not `<p>` tags for better mobile rendering)
- Inline styles use `style="..."` attributes directly on elements
- Images embedded as `<img src="...">` with base64 or eBay-hosted URLs

### Dependencies
- Rendered by: `backend/app/services/template_manager.py:TemplateManager.render_template()`
- Variables populated by: `backend/app/services/processor_service.py` during listing creation
- Used in: Trading API `AddFixedPriceItem` XML as the `Description` field
- Input sanitization: `backend/app/core/validators.py` sanitizes before template interpolation

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
