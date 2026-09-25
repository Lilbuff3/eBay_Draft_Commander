## 2025-02-12 - MobileNavBar keyboard navigation
**Learning:** Found that the MobileNavBar tab buttons were using `focus-visible:outline-none` and missing a visual focus indicator for keyboard users.
**Action:** Applied `focus-visible:ring-2 focus-visible:ring-persimmon-500/50 rounded-xl` to the tab items to provide clear keyboard focus indicator consistent with other UI items while disabling default browser outlines.
