<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# listings

## Purpose
Active eBay listing management: the dead-stock inventory card and the review queue for paused listings. The old Inventory-API bulk edit/media path was removed — it never worked on Trading-API listings.

## Key Files

| File | Description |
|------|-------------|
| `InventoryCard.tsx` | Dead/Stale/Warm card — 1-tap Drop price (ReviseFixedPriceItem), Promote, End |
| `ReviewQueue.tsx` | Pending listings queue — batch approve/reject/edit, synced with Zustand store |

## For AI Agents

### Working In This Directory
- Selection state managed by parent (ActiveListings) via `selectedSkus: Set<string>`
- eBay title max: 80 chars — bulk edits truncate via `.substring(0, 80)`
- Description input sanitized via `sanitizeDescription()` on save
- ReviewQueue uses store actions: `approvePending`, `updatePending`, `deletePending`
- Media validation is client-side before upload
- Use `toast()` for notifications, not `alert()`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
