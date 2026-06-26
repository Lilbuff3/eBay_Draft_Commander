# Gemini Work Order — Promoted Listings (ad rate on new listings)

Written for a cold start. You have no memory of prior sessions; everything you
need is here. You are an LLM coding agent (Gemini, in Antigravity IDE) working in
the eBay Draft Commander repo.

## Goal

Add **eBay Promoted Listings** (pay-on-sale ads) to newly created listings, at a
configurable ad rate. This is the single biggest visibility lever on modern eBay —
promoted items can roughly double impressions. Cost is only incurred when an item
sells through the ad, so it's low-risk margin-wise.

## Current state (as of 2026-06-26)

- Repo: `C:\Users\adam\Projects\ebay-draft-commander`. Branch `master` is current
  and pushed. Full unit suite: **436 passing** (`pytest tests/unit -v`).
- Listings are created via the **Trading API** `AddFixedPriceItem`
  (`backend/app/services/ebay/trading.py:206` `add_fixed_price_item`), orchestrated
  by `backend/app/services/processor_service.py:452` `create_listing`. A successful
  create returns an eBay **ItemID** (the `listing_id`).
- Promoted Listings is **NOT implemented** — there is no marketing module today.
- eBay OAuth/token handling: `backend/app/services/ebay/auth.py` +
  `backend/app/core/token_manager.py`. eBay calls are rate-limited via
  `backend/app/core/rate_limiter.py` (`ebay` bucket).
- Settings are read/written via `backend/app/core/settings_manager.py` (SettingsManager
  singleton) and exposed at `backend/app/blueprints/api/settings_api.py`.

## HARD CONSTRAINTS — read before touching anything

1. **Do NOT touch live integration paths:** `integrations/hermes/**` and
   `%LOCALAPPDATA%\hermes\**`. They run the live WhatsApp pipeline.
2. **Branch from `master`.** Use `feature/promoted-listings`. Per-task commits.
   Push the branch. **Do NOT merge to master** — leave it for review.
3. **TDD every change.** Failing test first, watch it fail, minimal code to pass.
   Run `pytest tests/unit -v` after each task. No live eBay calls in unit tests —
   **mock the eBay HTTP client / Marketing API** (see existing eBay tests for the
   mocking style, e.g. `tests/unit/` files that test `ebay/` modules).
4. **Never edit `.env` directly** (a PreToolUse hook blocks it). Add settings via
   SettingsManager / settings_api.
5. The running app does **not** hot-reload Python. Don't restart it; your edits are
   inert until a restart (done at review time).

## eBay API background (Promoted Listings General)

- Promoted Listings is the **Sell Marketing API** (NOT part of AddFixedPriceItem).
- Flow: ensure a Promoted Listings **campaign** exists, then add the listing as an
  **ad** under it with a bid percentage (the ad rate). For Trading-API-created
  listings you have the `listing_id` (ItemID), so use the create-ad-by-listing-id
  path under a General campaign.
- **OAuth scope prerequisite:** the user token needs the `sell.marketing` scope.
  The current token may not have it. **Do not assume it works live** — write the
  code + mocked tests, and document in the PR that the eBay app/token must be
  re-consented with `sell.marketing` before this works against production.
- Verify exact endpoints/payloads via eBay's current Marketing API docs (use
  Context7 or eBay developer docs) — do not hardcode from memory.

## Tasks (each its own commit, TDD)

### Task 1 — Marketing API client
- **Create:** `backend/app/services/ebay/marketing.py` with a `MarketingAPI` class:
  - `ensure_campaign(self) -> str` — find or create a default Promoted Listings
    General campaign; return its campaign_id (cache it).
  - `promote_listing(self, listing_id: str, ad_rate_percent: float) -> dict` —
    add the listing as an ad under the campaign at the given bid percentage.
  - Use `auth.py` for the user OAuth token and the `ebay` rate-limit bucket.
- **Test:** mock the HTTP layer; assert the request URL/payload are well-formed,
  and that `promote_listing` returns a normalized success/failure dict.

### Task 2 — Settings
- Add `PROMOTED_LISTINGS_ENABLED` (default `false`) and
  `PROMOTED_LISTINGS_AD_RATE` (percent, default `5.0`) via SettingsManager, and
  surface them in `settings_api.py` read/write.
- **Test:** settings round-trip; invalid ad rate (e.g. negative, >100) rejected or
  clamped to a sane range.

### Task 3 — Hook into listing creation (failure-safe)
- In `processor_service.py` `create_listing` (line ~452), AFTER a successful
  create yields a `listing_id`, if `PROMOTED_LISTINGS_ENABLED` is true, call
  `MarketingAPI().promote_listing(listing_id, ad_rate)`.
- **Critical:** promotion failure must NEVER fail or block the listing — wrap in
  try/except, log, and continue. The listing succeeding is what matters.
- **Test:** (a) enabled → promote_listing called with the listing_id + configured
  rate; (b) disabled → not called; (c) promote_listing raises → create_listing
  still returns success.

### Task 4 (optional) — Frontend settings toggle
- Add an enable toggle + ad-rate input to the Settings page
  (`frontend/src/pages/Settings.tsx` and store). Run `npm run build` in `frontend/`
  before committing. Skip if time-constrained; backend is the value.

## Acceptance criteria

- `pytest tests/unit -v` green (436 baseline + your new tests).
- Each task its own commit on `feature/promoted-listings`. Push the branch. Do NOT
  merge to master.
- PR/handoff note documents the `sell.marketing` scope prerequisite and that live
  verification is pending token re-consent.
- No live eBay calls in tests; promotion is failure-safe.
