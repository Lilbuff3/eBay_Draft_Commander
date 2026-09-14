<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# pages

## Purpose
Top-level page components rendered by App.tsx based on `activeTab` state.

## Key Files

| File | Description |
|------|-------------|
| `Dashboard.tsx` | Main view — job queue grid, upload zone, job detail drawer, queue controls, bulk operations, scanner modal |
| `Settings.tsx` | Configuration — env vars editor via API, server restart with health polling, automation toggles (auto-publish, confidence, shipping) |
| `BatchScan.tsx` | Books tab — ISBN scan sessions, sticky condition, Draft All → create-from-metadata |
| `Sourcing.tsx` | Source tab — field buy/pass verdict from `/api/lookup/comps`, confidence badge, session totals |
| `Orders.tsx` | Orders cockpit — ship-by alerts, worst-first sort (read-only; shipping happens on eBay) |
| `Profit.tsx` | Profit tab — real net per sale from the ledger, COGS fill-in, what is working |

## For AI Agents

### Working In This Directory
- Pages pull shared state from `useCommanderStore` — don't duplicate state locally for shared data
- Real-time updates via `useJobSync()` hook — don't fetch jobs manually in pages
- Tab switching: `store.setActiveTab(tabName)` — persisted to localStorage
- Use `ConfirmDialog` for destructive actions (delete, clear, restart)
- Use `useIsMobile()` for responsive layout (MobileNavBar vs Sidebar)

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
