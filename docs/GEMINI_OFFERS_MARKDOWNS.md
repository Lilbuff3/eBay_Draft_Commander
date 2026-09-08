# Gemini Work Order — Offers to Watchers + Stale-Item Markdown Ladder

Written for a cold start. You have no memory of prior sessions; everything you
need is here. You are an LLM coding agent (Gemini, in Antigravity IDE) working in
the eBay Draft Commander repo.

## Goal

Convert "almost-sales" and dead stock into cash — two background behaviors:

- **A. Offers to watchers:** for active listings that have watchers but no sale,
  auto-send a discounted offer to interested buyers. eBay data shows these convert
  well.
- **B. Stale-item markdown ladder:** for listings live past N days with no sale,
  step the price down by a configured percentage (down to a floor), to restore
  velocity. Unsold inventory ties up capital = pure loss.

Both are **high-ROI** and run unattended.

## Current state (as of 2026-06-26)

- Repo: `C:\Users\adam\Projects\ebay-draft-commander`. Branch `master` is current
  and pushed. Full unit suite: **436 passing** (`pytest tests/unit -v`).
- Active-listing management already exists: `backend/app/blueprints/api/listings_api.py`
  and `backend/app/services/ebay/inventory.py` (+ `trading.py` `GetSellerList`
  read fallback). Listings are created via `trading.py` `AddFixedPriceItem`.
- **Background-service pattern already exists** — copy it:
  `backend/app/services/queue_manager.py:174` `_init_background_services` spins up
  daemon threads (`_token_maintainer`, `_watch_inbox`) with a sleep loop. Your
  scanner thread should follow this exact pattern.
- eBay auth: `ebay/auth.py` + `core/token_manager.py`. Rate limiting:
  `core/rate_limiter.py` (`ebay` bucket — respect it).
- Settings: `core/settings_manager.py` + `blueprints/api/settings_api.py`.
- Offers / Negotiation / price-revision are **NOT implemented** today.

## HARD CONSTRAINTS — read before touching anything

1. **Do NOT touch live integration paths:** `integrations/hermes/**` and
   `%LOCALAPPDATA%\hermes\**`.
2. **Branch from `master`.** Use `feature/offers-markdowns`. Per-task commits. Push
   the branch. **Do NOT merge to master.**
3. **TDD every change.** Failing test first. Run `pytest tests/unit -v` after each
   task. **No live eBay calls in unit tests — mock the eBay client.** Markdown math
   must be a pure, unit-tested function with no eBay dependency.
4. **Never edit `.env` directly** (PreToolUse hook). Use SettingsManager.
5. **SAFETY: default everything to DRY-RUN.** The scanner must default to computing
   and logging actions WITHOUT calling eBay, until the owner explicitly enables
   live mode via settings. This is real money + real buyer-facing offers.
6. App does not hot-reload; don't restart it.

## eBay API background

- **Offers:** Sell **Negotiation API** — `findEligibleItems` then
  `sendOfferToInterestedBuyers`. Needs `sell.negotiation` OAuth scope.
- **Price revision (markdown):** Trading API `ReviseFixedPriceItem` (set a new
  `StartPrice` for the ItemID). Check whether a revise-price method already exists
  in `trading.py`/`inventory.py`; add one if not.
- **Listing age + watcher count:** source from `GetSellerList` (Trading) or the
  existing active-listings path in `inventory.py`/`listings_api.py`. Inspect what
  fields are already available before adding new calls.
- **Scopes prerequisite:** `sell.negotiation` (offers) and `sell.inventory`
  (revise). The current token may lack these. Write code + mocked tests; document
  in the PR that the token must be re-consented with these scopes before live use.
- Verify exact endpoints/payloads via current eBay docs (Context7 / eBay developer
  docs) — do not hardcode from memory.

## Tasks (each its own commit, TDD)

### Task 1 — Markdown math (pure, no eBay)
- **Create:** a pure function, e.g. `pricing` helper or
  `backend/app/services/markdown_engine.py`:
  `compute_markdown(original_price, current_price, days_live, *, after_days, step_pct, floor_pct) -> Optional[float]`
  → returns the new price if a markdown is due (live ≥ after_days, not yet at
  floor), else `None`. Never returns below `original_price * floor_pct/100`.
- **Test:** due vs not-due; step applied once; floor enforced; idempotent at floor.

### Task 2 — Negotiation API client
- **Create:** `backend/app/services/ebay/negotiation.py` with `NegotiationAPI`:
  `find_eligible_items(self) -> list` and
  `send_offer_to_interested_buyers(self, listing_id, discount_pct, message) -> dict`.
  Use `auth.py` + `ebay` rate bucket.
- **Test:** mock HTTP; assert request shape + normalized result; eligibility parsing.

### Task 3 — Revise-price (markdown execution)
- Add/verify a `revise_price(item_id, new_price)` method (Trading
  `ReviseFixedPriceItem`) in `trading.py` (or `inventory.py`).
- **Test:** mock; assert the XML/payload sets the new StartPrice for the ItemID.

### Task 4 — Background scanner thread (DRY-RUN default)
- Following the `_init_background_services` daemon pattern in `queue_manager.py`,
  add a periodic scanner (e.g. once daily) that:
  1. Lists active listings with age + watcher count.
  2. For items with watchers ≥ `OFFER_MIN_WATCHERS` and no sale → (live mode) send
     offer at `OFFER_DISCOUNT_PCT`; (dry-run) log only.
  3. For items live ≥ `MARKDOWN_AFTER_DAYS` → compute markdown (Task 1); (live)
     revise price (Task 3); (dry-run) log only.
  - **Idempotency:** track which listings were offered/marked-down (and when) in the
    DB so the same buyers aren't re-offered and prices don't double-step in one
    cycle. Add a small table or reuse `job_metadata`.
- **Test:** with a mocked listing set, assert correct actions chosen in dry-run
  (logged, no eBay calls) and that live mode calls the mocked clients exactly once
  per eligible item. Floor + idempotency respected.

### Task 5 — Settings
- Via SettingsManager + settings_api: `OFFERS_ENABLED` (default false),
  `OFFER_DISCOUNT_PCT` (default 10), `OFFER_MIN_WATCHERS` (default 1),
  `MARKDOWN_ENABLED` (default false), `MARKDOWN_AFTER_DAYS` (default 14),
  `MARKDOWN_STEP_PCT` (default 5), `MARKDOWN_FLOOR_PCT` (default 70),
  `OFFERS_MARKDOWNS_DRY_RUN` (default **true**).
- **Test:** round-trip + bounds validation.

## Acceptance criteria

- `pytest tests/unit -v` green (436 baseline + your new tests).
- Each task its own commit on `feature/offers-markdowns`. Push the branch. Do NOT
  merge to master.
- Dry-run is the default; live actions only behind explicit settings.
- PR/handoff note documents the `sell.negotiation` + `sell.inventory` scope
  prerequisites and that live verification is pending token re-consent.
- No live eBay calls in tests.
