## 2023-10-14 - Ensure Interactive Elements have Keyboard Focus
**Learning:** The custom hover states like `sm:group-hover:opacity-100` can cause elements to be completely inaccessible to keyboard users if a corresponding `focus-visible` class is not applied.
**Action:** Always verify that interactive elements hidden behind hover states on desktop are also visible when receiving focus via keyboard navigation by adding `sm:focus-visible:opacity-100` along with standard focus rings.
