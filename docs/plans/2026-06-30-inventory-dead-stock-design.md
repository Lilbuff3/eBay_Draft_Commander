# Inventory: Dead-Stock Cockpit — Design

## Context

The Inventory tab renders blank: `/api/listings/active` returns 89 listings with eBay
status `'Active'` (Trading API, via the `GetSellerList` fallback because listings are
created with `AddFixedPriceItem`, not the Inventory API), but `ActiveListings.tsx` only
shows rows where `status === 'PUBLISHED'`. So every row is filtered out.

The user is a WhatsApp-first reseller who checks the app on mobile. Goal: turn Inventory
into a **dead-stock cockpit** — surface listings rotting unsold (old + unwatched = frozen
capital) and let the user fix them (drop price / promote / end) in one tap, on a phone.

Signal is **age + watchers only** — eBay deprecated per-listing views (HitCount), so no
fake views number.

## Backend

1. **Watchers + age** — in the `GetSellerList` path (`ebay/inventory.py` fallback →
   `ebay/trading.py:get_active_listings_light`), add OutputSelectors
   `ItemArray.Item.WatchCount` and `ItemArray.Item.ListingDetails.StartTime`; parse into each
   listing dict as `watchCount` (int) and `startTime` (ISO string). Same call → no extra
   rate-limit cost. `/api/listings/active` passes them through.

2. **Reprice (new)** — `revise_fixed_price_item(item_id, price, qty=None)` in `trading.py`
   (Trading XML `ReviseFixedPriceItem`), mirroring `end_fixed_price_item` (token refresh on
   401, error parse). Route: `POST /api/listings/<itemId>/price` `{price}`. Failure-safe.

3. **Action routes (wrap existing services)** —
   `POST /api/listings/<itemId>/end` → `ebay_service.end_listing` (`end_fixed_price_item`).
   `POST /api/listings/<itemId>/promote` → `marketing.promote_listing` at
   `PROMOTED_LISTINGS_AD_RATE`.

4. **Env thresholds** — `DEAD_STOCK_AGE_DAYS` (60), `STALE_AGE_DAYS` (30), `WARM_WATCHERS` (3).

## Staleness model (frontend-derived from age + watchers)

- 🔴 **Dead** — ageDays > 60 AND watchCount === 0
- 🟠 **Stale** — ageDays > 30 AND watchCount <= 1 (not Dead)
- 🟢 **Warm** — watchCount >= 3
- **OK** — rest

Default sort: Dead → Stale → age desc (worst-first). Toggles: age / price / watchers.

## Frontend (`ActiveListings.tsx` + new `listings/` pieces)

- **Fix blank:** treat both `'Active'` and `'PUBLISHED'` as active.
- **Capital banner:** `Σ price` over Dead → "$X tied up · N dead (>60d, 0 watchers)". Tap →
  filter Dead. Smaller Stale subtotal line.
- **Filter chips:** All · Dead(N) · Stale(N) · Warm(N), live counts.
- **Mobile-first cards** replace the desktop table: photo, title, price, chip row
  (`47d` · `👁 0` · tag). Scale up fine on desktop.
- **1-tap actions per card:**
  - Drop price → presets (−10/−15/−20%) or typed → `POST /price` → in-place update (reversible).
  - Promote → confirm (costs %/sale) → `POST /promote` → toast.
  - End → confirm dialog (destructive) → `POST /end` → row drops.
- Failure-safe: error → toast → revert. Reuse `BulkActionBar` for optional bulk drop/end.

## Verification

- `curl /api/listings/active` → each listing has `watchCount` + `startTime`.
- `curl -XPOST /api/listings/<id>/price -d '{"price":..}'` on a test item → 200, price changes,
  then revise back.
- Mobile screenshot (390px, fresh browser via playwright-skill): cards render, capital banner
  shows, Dead/Stale tags correct, no console errors.
- `npm run build` clean (tsc passes).

## Out of scope (later)

Per-listing real views (needs Analytics getTrafficReport). Auto-reprice/auto-end. Price-vs-comp
suggestions on each card.
