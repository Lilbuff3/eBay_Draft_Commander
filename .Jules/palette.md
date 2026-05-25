## 2026-05-25 - Adding ARIA labels to icon-only buttons
**Learning:** In standard frontend components, icon-only buttons can omit `aria-label` attributes causing accessibility issues for screen readers. In `ListingRow.tsx` and `MediaManager.tsx`, several icon buttons for actions like Edit, Save, Delete/Remove lacked labels.
**Action:** Always ensure `aria-label` attributes are added when using `size="icon"` or buttons containing only icons, such as `<RefreshCw />` or `<X />`.
