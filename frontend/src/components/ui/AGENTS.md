<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# ui

## Purpose
shadcn/Radix UI primitives with CVA (class-variance-authority) variant system. Consistent, accessible design tokens used throughout the app.

## Key Files

| File | Description |
|------|-------------|
| `button.tsx` | Variants: default, destructive, outline, secondary, ghost, link. Sizes: sm, default, lg, icon. |
| `input.tsx` | Text input with focus/error states |
| `label.tsx` | Form label with optional required indicator |
| `card.tsx` | Card container with Header, Title, Description, Content, Action, Footer sub-components |
| `dialog.tsx` | Modal dialog (Radix Dialog) with header/content/footer |
| `textarea.tsx` | Multi-line input with auto-resize |
| `select.tsx` | Dropdown with option groups and searchable filtering |
| `tabs.tsx` | Tab navigation with content panels |
| `badge.tsx` | Status indicators (success, warning, info, destructive) |
| `scroll-area.tsx` | Custom scrollbar container |
| `slider.tsx` | Range slider for numeric input |
| `table.tsx` | Table structure components |
| `sheet.tsx` | Side sheet/drawer (slides from edge) |

## For AI Agents

### Working In This Directory
- CVA pattern: `cva(baseClasses, { variants: { variant: {...}, size: {...} } })`
- Merge classes with `cn()` from `@/lib/utils` (clsx + tailwind-merge)
- Never remove Radix props — they provide ARIA, keyboard nav, focus management
- `data-slot` attributes for testing/style targeting
- `asChild` prop for polymorphic rendering (e.g., Button wrapping an `<a>`)
- Focus: use `focus-visible` (not `focus`), ring pattern: `focus-visible:ring-ring/50 focus-visible:ring-[3px]`
- Disabled: `disabled:pointer-events-none disabled:opacity-50`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
