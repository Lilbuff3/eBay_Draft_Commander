## 2024-05-14 - Icon-only buttons lacking ARIA labels
**Learning:** React components containing icon-only buttons (like `lucide-react` icons inside Radix/Tailwind buttons) often lack text equivalents, rendering them invisible or unhelpful to screen readers.
**Action:** Always provide an explicit `aria-label` attribute (and often a `title` attribute for mouse users) when using `size="icon"` or similar patterns without visible text inside interactive elements.
