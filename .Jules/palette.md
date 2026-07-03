## 2024-05-18 - Added Accessibility Labels to Icon-Only Buttons
**Learning:** Found several icon-only `<Button>` elements (e.g., using `size="icon"`) in modals and rows that lacked `aria-label` or `title` attributes, which would prevent screen readers from understanding their action and hide tooltips from mouse users. This seems to be a common pattern when quickly scaffolding UI components in this app.
**Action:** Always add `aria-label` and `title` to `<Button size="icon">` elements moving forward, ensuring the labels are contextual (e.g. `aria-label={"Remove " + item.title}`).
