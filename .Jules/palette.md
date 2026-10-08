## 2026-10-08 - Focus visibility on hover-only elements
**Learning:** Elements that are hidden on desktop until hovered (e.g., using `sm:opacity-0 sm:group-hover:opacity-100`) remain invisible during keyboard navigation unless explicitly revealed, making them completely inaccessible to keyboard users who can't see what they've focused.
**Action:** When adding `sm:opacity-0 sm:group-hover:opacity-100` to interactive elements, always pair it with `sm:focus-visible:opacity-100` and appropriate `focus-visible:ring` styles so the element appears when tabbed to.
