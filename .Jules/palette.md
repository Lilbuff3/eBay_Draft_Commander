## 2026-10-31 - Accessible DndKit Sortable Thumbnails
**Learning:** When building DndKit sortable lists using generic `<button>` elements, they do not inherently have accessible names for screen readers unless explicitly provided, and focus states are often missed leading to poor keyboard navigation.
**Action:** Always add explicit `aria-label` (e.g. `Select image ${index + 1}`), `aria-pressed` attributes, and `focus-visible` utility classes to sortable items.
