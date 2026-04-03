## 2024-04-03 - Add ARIA label to Active Listings Refresh Button
**Learning:** Icon-only buttons used for frequent actions (like a refresh button) lacked ARIA labels.
**Action:** Always verify icon-only buttons have an `aria-label` attribute when using components like `<Button variant="ghost" size="icon">`.
