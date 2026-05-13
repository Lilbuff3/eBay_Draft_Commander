## 2024-05-01 - Missing ARIA labels on icon-only buttons
**Learning:** Radix UI / Shadcn UI `size="icon"` Button components in this codebase frequently omit the `aria-label` attribute by default. This causes screen readers to announce unhelpful text like "button" instead of describing the action (e.g., "Refresh listings", "Zoom out").
**Action:** Always explicitly verify that `<Button size="icon">` includes an `aria-label` attribute, especially for critical actions like closing modals, zooming, or refreshing data.
