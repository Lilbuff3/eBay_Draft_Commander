
## 2024-10-09 - Ensure Hover-Reveal Elements Are Keyboard Accessible
**Learning:** Elements that are hidden until hover on desktop (e.g., using `sm:opacity-0 sm:group-hover:opacity-100`) become invisible to keyboard users navigating via Tab if they aren't explicitly revealed on focus. They might receive focus natively, but the user cannot see where they are on the screen.
**Action:** When adding accessibility focus states to interactive elements that are hidden until hover, ensure they also become visible on keyboard focus by adding classes like `sm:focus-visible:opacity-100`.
