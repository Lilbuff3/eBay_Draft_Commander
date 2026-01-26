# SOP: Stylize & Templates

## Purpose
To ensure every listing uses a professional, mobile-responsive HTML layout.

## The Separation of Concerns
1.  **Data Template**: Stored in `data/templates.json` (or DB). Defines *Business Logic* (Condition, Shipping Policy, Return Policy).
2.  **Visual Template**: Stored in `templates/`. HTML files with placeholders (e.g., `{{TITLE}}`, `{{DESCRIPTION}}`, `{{IMAGES}}`).

## The Rendering Pipeline
1.  **Select Template**: User chooses "Industrial Electronics" (Data) + "Professional Mobile" (Visual).
2.  **Merge Data**:
    - `{{TITLE}}` -> Listing Title
    - `{{DESCRIPTION}}` -> Raw Text Description (from User/AI)
    - `{{ASPECTS}}` -> HTML Table of Item Specifics
    - `{{IMAGES}}` -> HTML Grid of Image URLs
3.  **Output**: A single HTML string injected into the `InventoryItem.product.description` field.

## Mobile-First Rules
- **Viewport**: Always include `<meta name="viewport" content="width=device-width, initial-scale=1">`.
- **CSS**: Use internal `<style>` blocks (eBay strips external CSS).
- **Images**: `max-width: 100%; height: auto;`.
- **Fonts**: Use sans-serif (Arial, Helvetica, Verdana) for readability. No tiny fonts (< 14px).
