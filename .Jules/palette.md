## 2024-05-18 - Keyboard Accessibility for Hover-Hidden Interactive Elements
**Learning:** Interactive elements hidden until hover on desktop (e.g., `sm:opacity-0 sm:group-hover:opacity-100`) become inaccessible to keyboard users because they remain visually hidden even when focused.
**Action:** Always pair `sm:group-hover:opacity-100` with `sm:focus-visible:opacity-100` and explicit focus rings (e.g., `focus-visible:ring-persimmon-500`) to ensure they become visible upon keyboard navigation.
