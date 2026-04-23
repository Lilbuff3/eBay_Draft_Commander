## 2025-04-23 - Added ARIA labels to icon-only buttons
**Learning:** Found multiple instances across the frontend components (`ActiveListings`, `AnalyticsDashboard`, and `ListingRow`) where icon-only buttons lacked `aria-label`s. This is a common accessibility anti-pattern.
**Action:** Ensure all icon-only buttons have descriptive `aria-label` attributes to maintain screen reader accessibility.
