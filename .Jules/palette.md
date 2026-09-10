## 2024-05-18 - Added `aria-label` to Close Button in `MigrationModal.tsx`
**Learning:** Icon-only buttons used for closing dialogs or dismissing elements (often using an "X" icon like `lucide-react`'s `X`) frequently miss `aria-label`s, negatively impacting screen reader accessibility because their purpose is only visual.
**Action:** Always ensure that `<Button size="icon">` or generic `<button>` components containing solely an icon receive an explicitly descriptive `aria-label` (e.g., `"Close"` or `"Dismiss"`).
