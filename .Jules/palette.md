## 2023-10-27 - Focus States for Interactive Elements
**Learning:** Adding `focus-visible` to custom `<button>` elements, interactive `div` elements, and generic interactive anchors significantly improves keyboard navigation without degrading mouse user experience. Custom UI frameworks often strip focus states, making the app inaccessible to keyboard-only users.
**Action:** Always add `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color]-500` (matching the element's context or project accent) to interactive elements that lack them.
