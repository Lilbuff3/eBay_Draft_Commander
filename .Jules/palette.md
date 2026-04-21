## 2026-04-21 - Icon-Only Button Accessibility
**Learning:** Icon-only UI components using Radix-based `<Button size="icon">` frequently omit the `aria-label` attribute by default, breaking basic keyboard and screen reader accessibility.
**Action:** Always ensure that icon-only interactive elements (like close buttons, refresh buttons, or FABs) include an explicit, descriptive `aria-label` string when they don't contain textual content.
