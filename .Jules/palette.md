## 2026-10-11 - Keyboard Focus Visibility
**Learning:** Interactive elements hidden behind hover states (e.g. `sm:opacity-0 sm:group-hover:opacity-100`) become inaccessible to keyboard users because tabbing to them keeps them hidden.
**Action:** Always add a corresponding focus-visible utility (e.g. `sm:focus-visible:opacity-100`) alongside desktop hover reveal classes to ensure keyboard navigation remains visible.
