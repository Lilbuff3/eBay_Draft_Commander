
## 2024-05-14 - Modal & Panel Close Buttons (ARIA)
**Learning:** Icon-only close buttons in secondary modals (Migration, Preview, Template, Price Research) are commonly missing `aria-label` attributes across the application, reducing screen reader accessibility.
**Action:** Audit and ensure all `variant="ghost" size="icon"` close buttons include explicit `aria-label` (e.g., "Close preview panel") and `title` attributes.
