## 2025-02-23 - Proper keyboard accessibility for custom dismiss/close actions
**Learning:** `div` and `motion.button` wrappers acting as dismiss buttons (e.g. `InstallPrompt.tsx` and `UploadZone.tsx`) lacked `focus-visible` classes and explicit keyboard event listeners. Custom click handlers on non-native buttons don't fire automatically on `Enter`/`Space`.
**Action:** Always add `tabIndex={0}`, an explicit `onKeyDown` handler (for `Enter` and `Space`), and `focus-visible` styling when using generic wrappers (`div`, `span`) or specific Radix/Framer elements as standalone interactive buttons.
