<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# item-detail

## Purpose
Specialized components for the job detail drawer: description display and scheduled listing time selection.

## Key Files

| File | Description |
|------|-------------|
| `ItemDescriptionCard.tsx` | Read-only HTML description with sanitization (XSS prevention), prose styling, 500-char truncation |
| `ItemScheduleField.tsx` | Datetime picker with preset buttons (Sun/Mon/Wed evening), UTC-aware min/max validation, eBay 48-hour lead time |

## For AI Agents

### Working In This Directory
- Always sanitize HTML via `@/lib/sanitizer` before `dangerouslySetInnerHTML`
- Schedule field uses UTC internally, displays in user's local timezone
- eBay constraints: 48-hour minimum lead time, 21-day maximum
- Preset scheduling targets ~7PM Pacific for peak listing times
- Components call `updateDraft()` callback to persist input to parent (ItemDetailDrawer)

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
