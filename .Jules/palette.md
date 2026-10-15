## 2024-10-15 - Elements hidden with opacity-0 needing focus-visible:opacity-100
**Learning:** Interactive elements hidden with `opacity-0` (or `sm:opacity-0 sm:group-hover:opacity-100`) to declutter the UI on desktop are completely inaccessible to keyboard users because they remain invisible when tabbed to.
**Action:** When adding `opacity-0` to hide interactive elements until hover, ALWAYS add a corresponding `focus-visible:opacity-100` (e.g. `sm:focus-visible:opacity-100`) along with `focus-visible:ring-2` to ensure they become visible and clearly focused during keyboard navigation.
