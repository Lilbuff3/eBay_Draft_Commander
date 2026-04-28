## 2024-05-18 - Missing ARIA labels in Data Grids
**Learning:** Found multiple instances of icon-only action buttons (Edit, Cancel, Relist, Link) inside data grids (ListingRow) missing `aria-label`s. This is a common pattern where developers focus on the visual representation of table actions but overlook screen reader accessibility.
**Action:** When reviewing table/grid components, specifically check the trailing "Actions" column for icon-only buttons to ensure they have descriptive labels.
