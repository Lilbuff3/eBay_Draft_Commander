
## 2024-06-03 - Missing ARIA Labels on Radix UI Button Components
**Learning:** Custom UI components wrapper like `Button` with `size="icon"` are frequently used across the app but often omit `aria-label`s. Because these buttons only contain icons (like `<Trash2 />` or `<X />`) and no text children, they are completely invisible or unhelpful to screen reader users, violating accessibility guidelines.
**Action:** When reviewing table or data grid components, or any modal/panel headers, specifically check for `Button` components using `size="icon"` and ensure they have descriptive `aria-label` attributes.
