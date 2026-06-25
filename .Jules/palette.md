## 2024-06-25 - Icon-only buttons lacking ARIA labels
**Learning:** React components using Button with size="icon" (like in dialog headers, zoom controls, and delete buttons) frequently lack aria-label or title attributes, severely reducing accessibility for screen reader users who only hear "Button" instead of the action it performs.
**Action:** Add descriptive aria-label attributes to all icon-only buttons across components, particularly those used for standard interactions like closing modals, zooming, or deleting items.
