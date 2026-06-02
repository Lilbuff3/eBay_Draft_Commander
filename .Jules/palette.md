## 2024-05-15 - Missing ARIA Labels on Icon Buttons
**Learning:** Icon-only buttons (like those using `<Button size="icon">` in the Actions columns) frequently lack `aria-label` attributes, creating a significant accessibility gap for screen reader users. The `title` attribute is often used for tooltips, but `aria-label` is still essential for robust accessibility.
**Action:** When implementing or reviewing icon-only buttons, specifically check the trailing actions columns (like in tables or lists) to ensure they have descriptive `aria-label` attributes.
