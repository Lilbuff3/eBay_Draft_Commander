## $(date +%Y-%m-%d) - Add ARIA Labels to Icon-Only Buttons
**Learning:** Found multiple instances where the `<Button size="icon">` UI component was used without an accompanying `aria-label`, compromising screen reader accessibility across modals, grids, and tables.
**Action:** Always verify icon-only buttons have descriptive `aria-label` attributes.
