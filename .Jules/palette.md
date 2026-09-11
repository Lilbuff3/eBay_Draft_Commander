## 2024-09-11 - Add accessible labels to icon-only buttons
**Learning:** Found several generic icon-only buttons (`<Button size="icon">`) without `aria-label` or `title` attributes (e.g. MigrationModal, BatchScan, Sourcing). Without these labels, screen readers announce them generically as "button", creating an inaccessible experience for non-sighted users.
**Action:** When creating or reviewing components with `<Button size="icon">` (or similar visual-only interactive elements), strictly ensure that `aria-label` and `title` attributes are included to provide context and tooltips.
