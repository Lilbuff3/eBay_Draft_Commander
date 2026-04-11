
## 2024-04-11 - Empty States and Icon Buttons
**Learning:** Found several icon-only buttons (like `RefreshCw` and `X`) lacking `aria-label`s, which is a major accessibility issue for screen readers. Additionally, replacing generic text string empty states (like `{filteredListings.length === 0 ? "No active listings found" : ...}`) with dedicated visual empty states using existing `lucide-react` icons greatly improves the visual appeal.
**Action:** When working on lists or datagrids, always verify if the empty state is purely textual, and upgrade it to use a proper icon and secondary helper text. Always add `aria-label="Action name"` and `aria-hidden="true"` to the inner icon of icon-only buttons.
