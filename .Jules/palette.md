## 2024-05-18 - Keyboard Accessibility in UploadZone
**Learning:** Adding `tabIndex={0}`, `role="button"`, and `onKeyDown` handlers correctly exposes a custom visual button/drop-zone as an interactive element to screen readers and keyboard users. `focus-visible:ring-2 focus-visible:ring-sage-500` seamlessly integrates the keyboard focus indicator using standard Tailwind classes.
**Action:** Always ensure custom interactive elements like drop zones or non-standard buttons have explicit keyboard interactions and visible focus indicators.
