<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# listings

## Purpose
Active eBay listing management: bulk actions, individual editing, media upload, and review queue for pending listings.

## Key Files

| File | Description |
|------|-------------|
| `BulkActionBar.tsx` | Animated action bar (Framer Motion slide-in) — bulk price, bulk title (Find & Replace/Append/Prepend), end listings |
| `EditListingDialog.tsx` | Modal with tabs: Details (title/price/qty), Media (upload), Description (HTML editing) |
| `MediaManager.tsx` | Drag-and-drop media upload — images (JPG/PNG/WebP) and videos (MP4/MOV, max 150MB) |
| `ListingRow.tsx` | Single listing row — title, price, thumbnail, SKU, quantity, selection checkbox |
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
