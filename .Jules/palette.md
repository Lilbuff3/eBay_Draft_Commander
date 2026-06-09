
## 2024-05-18 - Keyboard Accessibility for Drag-and-Drop Zones
**Learning:** Custom drag-and-drop zones implemented using generic `div` or `motion.div` elements completely lack keyboard accessibility by default. Users cannot tab to them or trigger them with Enter/Space without manual implementation, even if an `onClick` handler is attached to proxy to a hidden file input.
**Action:** When creating click-to-upload or drag-and-drop regions that proxy to hidden file inputs, always add `role="button"`, `tabIndex={0}`, an `onKeyDown` handler (for Enter/Space), and visible focus states (e.g., `focus-visible:ring-2 focus-visible:ring-sage-500`) to ensure they are accessible to keyboard and screen reader users.
