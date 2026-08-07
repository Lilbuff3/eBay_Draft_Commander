# eBay Draft Commander

AI-powered eBay listing automation. Flask backend + React TypeScript frontend PWA.

## Canonical Location

```
C:\Users\adam\Projects\ebay-draft-commander\
```

**All AI tools (Claude, Gemini, Zenflow, etc.) must work from this directory.** Never clone elsewhere. Feature branches for isolation, not separate clones.

## Workflow

- `master` is the default branch on GitHub
- Feature work: `git checkout -b feature/description` → develop → merge to master → push
- Never leave unpushed commits — push at end of each session
- Run `npm run build` in frontend/ before committing frontend changes

## Commands

```bash
# Backend
pip install -r requirements.txt
python backend/run_service.py             # Start server under supervisor (restartable, port 5000)
python backend/wsgi.py                     # Start server directly (no /restart support)
pytest tests/ -v                          # Run tests
python manage.py update_policies          # Fetch eBay policies to .env
python manage.py fix_publish <offer_id>   # Fix policies and publish offer

# Frontend
cd frontend && npm install
npm run dev                               # Vite dev server (port 5175, proxies /api to 5000)
npm run build                             # Build to ../static/app/
npm run test                              # Vitest

# Full stack dev
# Terminal 1: python backend/wsgi.py
# Terminal 2: cd frontend && npm run dev
```

## Architecture

```
backend/                    Flask app factory
  wsgi.py                   Direct server entrypoint (socketio.run, port 5000)
  wsgi_service.py           Headless launcher (stdout/stderr → data/backend_service.log)
  run_service.py            Supervisor: launches wsgi_service.py as a child, relaunches on exit-42 (powers /api/system/restart)
  mcp_server.py             Read-only eBay MCP server (search, category, aspects, price research, token status) for Claude Code
  app/
    __init__.py             create_app(), SocketIO singleton
    blueprints/
      api/                  REST API (split into modules)
        __init__.py         Blueprint registration, combines sub-modules
        jobs_api.py         /api/jobs CRUD, details, thumbnails
        queue_api.py        /api/queue control (start, pause, skip, retry)
        listings_api.py     /api/listings, active listing management
        settings_api.py     /api/settings read/write
        lookup_api.py       /api/lookup (book, ISBN, category)
        analytics_api.py    /api/analytics endpoints
        system_api.py       /api/system/* (health, restart, cache clear) — url_prefix='/system'
        migration_api.py    /api/migration/* — scan eBay for legacy active listings, flag untracked
        helpers.py          Shared utilities for API routes
      ui.py                 Serves React SPA at /app/, redirects / to /app/
    core/
      constants.py          CONDITION_MAP, CONDITION_ID_MAP, rate limits, model names
      database.py           SQLAlchemy models (JobModel, TemplateModel, OrphanedMedia, AppToken)
      models.py             InternalListing dataclass (adapter pattern)
      settings_manager.py   .env read/write singleton
      rate_limiter.py       Token-bucket (gemini: GEMINI_RPM_LIMIT env, default 60; ebay: 5 burst)
      token_manager.py      Centralized eBay access token management (SQLite-backed)
      validator.py          Input validation (price, title, ISBN, paths)
      paths.py              Cross-platform path resolution
      exceptions.py         Custom exception hierarchy
      logger.py             Logging configuration
      prompts.py            AI prompt templates
      results_logger.py     JSONL listing outcome logger (data/listing_results.jsonl)
    services/
      queue_manager.py      Job lifecycle, background threads, Socket.IO events
      listing_ai_agent.py   AI-powered listing creation orchestrator
      scanner_service.py    Inbox folder scanning and detection
      ai_analyzer.py        Google Gemini vision + research
      ai_price.py           AI-assisted pricing
      pricing_engine.py     Market research pricing with fallback chain
      ebay_service.py       eBay API facade
      category_mapper.py    eBay category taxonomy mapping
      template_manager.py   HTML description template rendering
      image_processor.py    Image processing, background removal, upload
      processor_service.py  Main processing orchestrator (AI, category, pricing, upload)
      image_service.py      Image upload coordination
      isbn_scanner.py       ISBN barcode detection
      book_service.py       Book-specific metadata lookup
      item_specifics_mapper.py  eBay item specifics mapping
      listing_guardrails.py  Pre-listing quality guards: photo-hash dedup, price sanity, title/brand hygiene
      whatsapp_notify.py    Back-channel to the Hermes WhatsApp bridge /send (auto-decide + tell me)
      ebay/                 eBay REST/XML API modules
        auth.py             OAuth token management
        browse.py           Browse API (client credentials auth)
        inventory.py        Inventory API (existing listing management)
        media.py            EPS image upload
        trading.py          Trading API XML (AddFixedPriceItem, GetSellerList)
        taxonomy.py         Category taxonomy API
        policies.py         Business policies API
        researcher.py       eBay market research
        analytics.py        Seller analytics API
        adapters.py         TradingAPIAdapter, InventoryAPIAdapter field mappers
        marketing.py        Promoted Listings (Marketing API: ensure_campaign, promote_listing)
frontend/                   React 18 + Vite + TypeScript
  src/
    App.tsx                 Tab-based navigation via activeTab state, global layout
    store/
      useCommanderStore.ts  Single Zustand store (jobs, queue, settings, UI state)
    hooks/
      useJobSync.ts         Socket.IO real-time job synchronization
      useItemDraft.ts       Selected-job listing draft: details/images fetch, touched-field merge, submit
      useHaptics.ts         Mobile haptic feedback
    lib/
      api.ts                Typed fetch wrapper (apiFetch<T>)
      utils.ts              Shared utilities
      sanitizer.ts          Input sanitization
      pwa.ts                PWA install/update logic
    pages/                  Dashboard, Settings, BatchScan, Orders, Sourcing
    components/             30+ components
      ui/                   shadcn/Radix primitives
      item-detail/          Item description/specifics/schedule cards
      listings/             InventoryCard (dead-stock cockpit), ReviewQueue
```

## Key Patterns

- **Tab-based navigation** — `activeTab` state in `useCommanderStore`, persisted to localStorage. No react-router.
- **Code-split tab bodies** — `App.tsx` `React.lazy()`s every tab body except the landing `Dashboard` (eager), wrapped in one `<Suspense fallback={<PageLoader/>}>`. Keeps heavy deps (dnd-kit → PhotoEditor drawer, zxing → scanner) off cold load: eager JS ~659KB vs ~1175KB unsplit. **Don't statically import a tab body into eager code** (App shell, Dashboard, home widgets) — it defeats the lazy split. Shared bits like `CONDITION_OPTIONS` live in `lib/conditions.ts` so lazy pages don't import each other. `vite.config.ts` `manualChunks` splits only *provably-eager* framework vendors (react, framer-motion, socket.io) for cross-deploy caching — **never manualChunk an async-only dep** (e.g. zxing): naming it promotes it into the initial graph and un-lazies it.
- **Zustand for state** — Single store (`useCommanderStore.ts`) manages jobs, queue status, settings, selected job, UI state. Accessed via selectors.
- **Typed HTTP client** — `apiFetch<T>()` in `src/lib/api.ts` wraps fetch with generics and error handling.
- **Socket.IO events**: `job_added`, `job_update`, `job_log` — emitted by QueueService, consumed via `useJobSync` hook.
- **Condition priority chain** — user_override > metadata > folder_name (CONDITION_MAP) > **AI-detected** > DEFAULT_CONDITION. AI refinement in `_refine_condition_from_ai()` only fires when no explicit override exists.
- **SKU format**: `DC-{8 uppercase hex}` generated in listing pipeline
- **Listing creation uses Trading API** — `AddFixedPriceItem` (XML), not Inventory API. Supports `ScheduleTime` for scheduled listings.
- **Scheduled listings** — Dashboard has datetime picker; `scheduled_time` stored on job, passed through to Trading API `ScheduleTime` field.
- **Job statuses**: pending, processing, completed, failed, paused, skipped, scheduled
- **API is modular** — `blueprints/api/` is a package with 8 sub-modules (jobs, queue, listings, settings, lookup, analytics, system, migration) plus `helpers.py`, not a single file.
- **Image reordering** — `ImageGallery` uses `@dnd-kit` drag-and-drop. `ordered_images` stored in `job_metadata`, respected by `image_processor.upload_images()`. First image = eBay cover photo.
- **Aspect schema** — `ebay_aspect_schema` (not old `ebay_required_aspects`) returns full required+optional aspects with `isRequired` flag. Dynamic refresh via `/api/lookup/category/<id>/aspects`. Fuzzy value matching in `processor_service._validate_and_enrich_specifics()`.
- **Background removal** — `image_processor.remove_background_and_square()` uses `rembg` + Pillow. Composites subject onto 2000x2000 white JPEG canvas. Originals preserved as `.orig` files.
- **3-phase AI pipeline** — Phase 1: Gemini vision analysis. Phase 2: Gemini with Google Search grounding (web research for specs, pricing, availability). Phase 3: aspect mapping with research-enriched prompts.
- **Smart title selection** — `listing_ai_agent.py` picks `max([seo_title, suggested_title], key=len)` — longer title = more descriptive for eBay SEO.
- **Required aspects guard** — `processor_service.py` validates required aspects before eBay submission. Auto-fills generic aspects (Brand, MPN, Type, UPC, etc.) with "Does Not Apply". Category-specific missing aspects route job to review instead of failing.
- **Results logging** — `results_logger.py` writes JSONL to `data/listing_results.jsonl`. Each record captures title, price, category, condition, comps, source, and outcome. Use `get_results()` and `compare_last_runs()` for analysis.
- **Pricing cascade (expanded)** — ISBN → MPN → Alt part numbers → Keywords → Research market price → Gemini grounding → AI estimate. Rarity-aware: rare/very_rare items use 75th percentile instead of median. Comps and reasoning persisted to job metadata.
- **ACTIVE_TO_SOLD_FACTOR** — comps come from Browse API = ACTIVE asking prices (NOT sold). `calculate_suggested_price` discounts the comp median by `ACTIVE_TO_SOLD_FACTOR` (env, default 0.87) toward estimated sold value. `median_price` field stays raw; only `suggested_price` is discounted. Only the `market_data_*` comp paths use it.
- **Seller notes** — free-text WhatsApp caption (minus the "sell" trigger) → `job_metadata['note']` → injected as trusted context into the AI vision prompt + pricing grounding estimate; surfaces in `description_html`. Helper `build_seller_note_block()` in `prompts.py`; empty note = no-op (prompts byte-identical). Capture note cleaned/capped (500 chars) by `_clean_capture_note` in `queue_api.py`.
- **Promoted Listings** — `ebay/marketing.py` `MarketingAPI` auto-promotes new listings at `PROMOTED_LISTINGS_AD_RATE`% (COST_PER_SALE) when `PROMOTED_LISTINGS_ENABLED=true`. Hook in `processor_service.create_listing` after a `listing_id` is obtained; **failure-safe** (promotion error never blocks the listing). Needs the `sell.marketing` OAuth scope on the user token.
- **Inventory dead-stock cockpit** — `/api/listings/active` (Trading-API `GetSellerList` fallback; listings carry status `'Active'`, not `'PUBLISHED'`) now also returns `watchCount` + `startTime` per listing (`WatchCount` + `ListingDetails.StartTime`, requested via `IncludeWatchCount` + `DetailLevel ReturnAll`). Frontend `lib/staleness.ts` derives **Dead** (>60d, 0 watchers) / **Stale** (>30d, ≤1) / **Warm** (≥3 watchers) — no views (eBay deprecated per-listing HitCount). `ActiveListings.tsx` is a mobile cockpit: capital-tied-up banner, Dead/Stale/Warm chips, worst-first sort, `InventoryCard` with 1-tap Drop price (ReviseFixedPriceItem) / Promote / End. The old Inventory-API edit/bulk path was removed (never worked on Trading-API listings).
- **Listing-quality guardrails** — `listing_guardrails.py` runs between AI/pricing output and eBay submit. **Auto-fix:** `clean_title` (dangling fragments, repeated words, ≤80), `normalize_aspects` (brand blocklist → "Unbranded", split "A / B"). **Route to `pending_review`:** photo-hash dedup (`compute_photo_hashes` dHash + `find_duplicate`, at capture in `queue_api`), and `check_price_sanity` (no-comp source over threshold, or >3× comp median, before `create_listing`). Photo hashes stored in `job_metadata['photo_hashes']`. Different photos never trip dedup → intentional variants safe.
- **Bulk book listing (Books tab)** — `BatchScan.tsx` at tab `batch-scan` (Sidebar + mobile nav "Books"). Capture: phone camera (`CameraBarcodeScanner.tsx`, native BarcodeDetector ean_13 — needs HTTPS/secure context; unsupported browsers fall back to USB wedge scanner/typing) or USB scanner (global keydown). Shared helpers in `lib/isbn.ts` (normalize, validate, 3s `ScanDeduper`, WebAudio beep). **Condition sessions:** sticky "Scanning as" selector — each scan inherits it; per-item + set-all overrides remain. Draft All → `POST /api/jobs/create-from-metadata` (also aliased at `/api/create-from-metadata`) per book with condition/price/category/item_specifics/pricing_data + `user_approved` (skips price-sanity review bounce), optional real photo rides along as **multipart** (`payload` JSON field + `photo` file — bundled to avoid the running-queue race), then `startQueue()`. Backend: `cover_service.py` fetches Open Library `-L` cover by ISBN (falls back to Google thumbnail, upscales to ≥500px for eBay, saves `cover.jpg`); `photo_1.*` sorts after `cover.jpg` so cover stays picture #1. **Vision skip:** batch_scan jobs get pre-seeded `ai_json` (`listing` key → `listing_ai_agent` cached path, `identification.category_id` 267 + isbn → Media Mail), pricing re-runs ISBN comps at the real condition; table price becomes `user_price` override. No-barcode books → existing photo flow.
- **Orders cockpit (ship-by alerts)** — `GET /api/orders` (alias of `/api/analytics/orders`, eBay Fulfillment API) returns enriched orders: `itemTitle`, `legacyItemId`, `shipByDate` (from `lineItemFulfillmentInstructions`), `paidDate`, `thumbnailUrl` (joined to local jobs by `listing_id` in `analytics_api._attach_thumbnails`). Frontend: `pages/Orders.tsx` tab (worst-first sort via `lib/orderStatus.ts` shipTag: overdue/urgent/pending/done) + `home/OrderStats.tsx` dashboard banner (hidden when nothing to ship, red when overdue/urgent). Analytics tab retired 2026-07 (duplicated Orders+Profit); backend analytics_api stays for /api/orders + ledger sweep. MCP: `ebay_orders` tool in `mcp_server.py`. Read-only — shipping actions happen on eBay. Related: `GET /api/jobs` sweeps past-due `scheduled` jobs holding a `listing_id` to `completed` (`queue_manager.finalize_past_due_scheduled`).
- **Sourcing verdict (Source tab)** — field buy/pass scanner: `GET /api/lookup/comps?gtin=&condition=` (any ISBN-10/13, UPC-A, EAN-8/13) runs `PricingEngine.search_sold_listings` → `calculate_suggested_price` — **no Gemini, no book metadata on the hot path** (~1-2s) — then `services/sourcing.py compute_verdict()`: est_sold = median×ACTIVE_TO_SOLD_FACTOR → net after FVF/processing/ship → `max_buy = min(net − SOURCING_MIN_PROFIT, net / SOURCING_ROI_MULTIPLE)` (median-based on purpose; pipeline `suggested_price` returned separately as `would_list_at`). Tiers: BUY / THIN (<4 comps) / PASS (max_buy<$1, beats THIN) / NO_DATA. Knobs `SOURCING_MIN_PROFIT` (5), `SOURCING_ROI_MULTIPLE` (3, 0=off), `SOURCING_SHIP_COST` (5) — Settings → Automation, live-read. Frontend `pages/Sourcing.tsx` (tab `sourcing`, sidebar + mobile-nav left): `CameraBarcodeScanner` gained optional `formats`/`validate` props (defaults keep BatchScan byte-identical) + a **ZXing fallback** (`@zxing/browser` pinned `0.2.0` / `@zxing/library` `0.22.0` — peer-locked, don't bump library past 0.22) that lazy-loads (own ~448KB chunk, not in eager bundle) whenever the native `BarcodeDetector` is absent or doesn't cover **all** requested formats — fixes devices whose detector lacks `upc_a`. Native stays the fast-path when it fully covers; `isbn.ts isLikelyGtin()` accepts UPC-A/EAN-8/any-EAN-13; USB wedge + manual entry; session history in localStorage `sourcingHistory` with Bought/paid tracking + running totals; bought ISBN rows push a `'found'` BatchItem into `batchScanItems` ("Send to Books"). **Match-quality confidence:** `/lookup/comps` also returns `id_type` (isbn/upc), `confidence` (high/medium/low), `confidence_reason` — `compute_verdict` grades trust from id_type (ISBN=book=high-trust since eBay listings reliably contain the ISBN vs UPC=looser), comp_count, and price spread (>6× low→high = "wide spread, comps may not match"). `Sourcing.tsx` renders a badge: green "Confident" for exact-ID, amber/red "Rough estimate — treat as a ballpark" otherwise — a keyword/loose match never shows as a firm price. **Accuracy tool:** `tools/accuracy_benchmark.py` re-runs the engine (`filter_comps` + identifier cascade) against ACTUAL sold prices (live Orders API or `--csv` Seller Hub export), splitting exact-ID vs keyword accuracy — the Gate-B moat test; ground truth is sold price, NOT `results_logger` (which logs list price at creation, not final sale). Tests: `tests/unit/test_sourcing.py`, `isbn.test.ts`.
- **Pricing confidence + comps-vs-AI arbitration** — the engine grades every price: `get_price_with_comps` returns `confidence` (high/medium/low/user) + `confidence_reason` on all paths. Shared grader `sourcing.assess_confidence(comp_count, prices, id_type, match_quality)` (public rename of the Source-tab `_assess_confidence`; `match_quality=None` keeps Source tab byte-identical). `filter_comps(with_meta=True)` returns `(comps, {match_quality, junk_removed})` — `model_gated`/`exact_id` grade identity-trusted, `floor_fallback` caps at low. **Keyword arbitration:** non-high keyword comps get a second opinion via `_ai_cross_check` (Phase-2 research mid if present = free, else one Gemini grounding call, skipped on FAST_MODE); within `PRICE_AGREEMENT_RATIO` (env, 1.6) → corroborated, confidence bumped; further apart → **`source='market_ai_conflict'`: AI price pre-filled as `suggested_price`, `comp_price`+`ai_price` both returned, confidence low**. Exact-ID/MPN paths never arbitrate (no new Gemini calls for books). **Under-price gate:** `apply_pre_listing_guardrails` gained `confidence`/`confidence_reason` — `'low'` → `pending_review` (wins over price-sanity; `user_approved` still bypasses). Persisted to `ai_data['pricing_confidence'/'pricing_confidence_reason'/'pricing_conflict']`; review reason lands on `job.error_message` (rendered in ReviewQueue under the badge). Seam warning: new engine fields must be threaded through `get_final_pricing`'s projection in `listing_ai_agent.py` or they're silently dropped — enforced by `tests/unit/test_pricing_projection_seam.py`, which reads the engine's real return keys and fails on a drop.
- **WhatsApp pause + tell me (review texts)** — review routing used to assume someone watches the web Review Queue. Now any price flag (conflict, low confidence, price sanity) **pauses the job in `pending_review` AND texts** via `whatsapp_notify`: destination from `get_notify_destination(job_metadata)` — the originating WhatsApp chat for bridge jobs, else the owner chat in `WHATSAPP_NOTIFY_CHAT_ID` (Settings → Automation; empty = no texts for web jobs). This **replaced the old "price outlier → list anyway" auto-decide** — the text makes the review visible, so pausing no longer strands WhatsApp items. Duplicate → `skipped` auto-resolve is unchanged. Builders: `build_price_review_message` (conflict form shows both prices), `build_queue_summary_message` — queue drain sends an owner digest ("N listed ($X total), M held for price review") from `_process_queue`'s batch-complete block (counter `_batch_stats['review']`). Origin `{channel,chat_id,bridge_port}` persisted in `job_metadata['origin']` from `/api/capture`. All best-effort — **real delivery needs the Hermes bridge on port 3000**; if down, the pause still happens, the message is just dropped (logged to `whatsapp_notify.log`).
- **Best Offer everywhere** — `trading.py build_best_offer_xml()` adds `BestOfferDetails` + `ListingDetails` auto-accept/decline floors (`BEST_OFFER_ENABLED`/`_AUTO_ACCEPT_PCT` 90/`_AUTO_DECLINE_PCT` 60, floors clamped < StartPrice) to every AddFixedPriceItem. Categories that reject Best Offer trigger ONE strip-and-retry without the blocks (`best_offer_stripped: true` in the result) — the flag never bricks a listing. Wired in `processor_service._create_trading_api_listing` (`best_offer_decline_pct` param overrides the decline floor — used by price discovery).
- **Price-discovery mode (no-comp items)** — `price_discovery.py` (pure) + a branch in `processor_service.create_listing` strictly AFTER the `user_approved` bypass: a no-comp AI-priced item (sources `ai_grounded_research`/`research_market_price`/`ai_estimate`, comps empty) lists at max(research-range high, suggested×(1+`PRICE_DISCOVERY_MARKUP_PCT` 25%)) with Best Offer (decline floor `PRICE_DISCOVERY_DECLINE_PCT` 50%) + `job_metadata['price_discovery']` tag (aggressive markdown ladder) instead of stalling in review; owner gets an inform-only WhatsApp text. `market_ai_conflict`, failed pricing, dups, user-approved keep old routing. `PRICE_DISCOVERY_ENABLED=false` restores byte-identical review behavior.
- **WhatsApp reply-to-review** — review texts end with 'Reply "ok"/number/"skip"'. Backend appends the job to `<captures>/.review_pending/<safe_chat>` (marker); the Hermes plugin intercepts ok/price/skip ONLY while a marker exists (normal chat never hijacked) → `capture_to_dc.py --review-reply` → `POST /api/review/reply` → `services/review_reply.py` (`parse_review_reply`, FIFO `resolve_pending_job` by origin chat, owner chat covers origin-less web jobs, shared `approve_job` also used by batch-approve). Marker entry popped on success. Plugin changes must stay additive + get deployed to `%LOCALAPPDATA%\hermes`.
- **Autopilot (offers + markdowns + relists)** — `autopilot_scanner.py`, daemon thread from `queue_manager._init_background_services`, fires daily after `AUTOPILOT_RUN_HOUR` (9). Per cycle: offers to watchers (`NegotiationAPI.send_offer`, one per price point, re-offer after a drop; `OFFER_MIN_WATCHERS`/`OFFER_DISCOUNT_PCT`), stale markdown ladder (`markdown_engine.compute_markdown`, `MARKDOWN_AFTER_DAYS` 14/`_STEP_PCT` 5/`_FLOOR_PCT` 70; discovery-tagged jobs use `DISCOVERY_MARKDOWN_*` 7/10/40), unsold relist sweep (`GetMyeBaySelling` UnsoldList → `RelistFixedPriceItem` with one step applied, `no_relist` blocklist rows written by `ebay_service.end_listing` so manual ends never resurrect, `RELIST_MAX_TIMES` 3, job `listing_id` rewritten to the new ItemID). **`OFFERS_MARKDOWNS_DRY_RUN` defaults true** — cycles record `listing_actions` rows + text an owner digest without touching eBay; live idempotency counts only live rows, so the dry window never suppresses the first real actions. Audit/idempotency table: `listing_actions` (ListingActionModel). Negotiation API needs only `sell.inventory` scope (already granted).
- **What's-working analytics + Today panel** — `LedgerService.get_performance` (`GET /api/ledger/performance?days=N`): sell-through rate, avg/median days-to-sell, revenue/net/ROI by category (from job ai_json identification) and by source (whatsapp/books/web); rendered on the Profit tab. `GET /api/today` (`today_api.py`, DB-only) feeds `home/TodayPanel.tsx`: last autopilot cycle (dry-run rows included = pre-flip audit) + live discovery-listing count.
- **ACTIVE_TO_SOLD_FACTOR is settings-editable** — tune it from real sales: `python tools/accuracy_benchmark.py --suggest-factor` (median actual/raw_median, exact-ID rows preferred, n<25 warned); set in Settings → Automation, restart to apply (constants.py reads env at import).
- **Mobile capture momentum loop** — `MobileCaptureSheet` is a two-phase state machine (`capture` ⇄ `success`): upload success shows an interstitial ("Item #N on its way", success haptic, session counter) with one-tap **Snap next item** (fires the camera input directly); condition stays sticky across items, category sticky in localStorage `dc-capture-category` (FAB skips CategoryPicker on repeat; header chip reopens it — picker renders AFTER the sheet in FAB JSX so it stacks on top). **Feedback ownership:** the sheet owns ALL upload feedback — `uploadFiles(..., {silent:true})` suppresses api-level toasts and Dashboard's old momentum toast is gone; don't re-add either. Exit animations require the `isOpen &&` check INSIDE `<AnimatePresence>` (early `return null` kills them).
- **Price explainer ("Why this price")** — `PriceExplainer.tsx` in ItemDetailDrawer: comp-spread range bar (median dot + your-price marker) + comp cards with thumbnails. Data path: `search_sold_listings` keeps `image_url` per comp; `calculate_suggested_price` returns `price_range [min,max]`; all market paths return `median_price`/`comp_count`/`price_range` → projected through `get_final_pricing` → persisted as `ai_data['pricing_median'/'pricing_range'/'pricing_comp_count']` → served in details `pricing_data.comps` (the old `comparables` key was never written — dead). Comps are ACTIVE asking prices — UI copy says so. Jobs processed pre-2026-07-17 have comps without `image_url` and null range (placeholder thumbs, no bar).
- **Profit ledger (Profit tab)** — real net per sale: `sales` table (SaleModel) snapshots eBay orders locally on every `/api/orders` fetch (`ledger.record_sales`, best-effort hook in `analytics_api`) so history outlives eBay's 90-day window. COGS = `job_metadata['cogs']`, captured three ways: WhatsApp caption token `paid X`/`cost X` (parsed by `_extract_cogs` in `queue_api.py` and **stripped from the note** so it never biases Gemini pricing), `cogs` field on `/api/job/<id>/update`, and Sourcing→Books flow-through (`cogs` in create-from-metadata payload). Frozen onto the sale row at sweep; resweeps backfill NULL cogs but never overwrite. `net = sale_total − FVF − $0.30 − SOURCING_SHIP_COST − cogs`; unknown COGS ⇒ `net: null` (first-class, amber "add cost" fill-in on the Profit tab writes via `POST /api/ledger/sales/<order_id>/cogs`). Endpoints: `/api/ledger/summary?weeks=N` (Monday-start weekly buckets), `/api/ledger/items` (thumbnail + days_to_sell enrichment via job join). Frontend `pages/Profit.tsx`, tab `profit`, desktop sidebar only. Sweep hardened: malformed order totals skipped, `sold_at` serialized with UTC suffix (naive ISO would parse as local time in JS). Tests in `tests/unit/test_ledger.py`.

## Database

SQLite at `data/commander.db`. ORM: SQLAlchemy. WAL mode enabled.

- **`jobs`** table (JobModel) — id (8-char hex PK), folder_path, status, scheduled_time, AI data + user overrides stored as JSON text columns (ai_json, item_specifics_json, metadata_json, timing_json)
- **`templates`** table (TemplateModel) — name (unique), data_json, use_count
- **`orphaned_media`** table — Tracks uploaded images from failed listings for cleanup
- **`app_tokens`** table — eBay access token persistence
- **`sales`** table (SaleModel) — local sold-order snapshots for the profit ledger: order_id PK, listing_id/job_id join keys, sale_total, sold_at, frozen fees_est/ship_est/cogs

SQLite pragmas: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`

## Processing Pipeline

1. Images in `inbox/` → ScannerService detects → creates job
2. ListingAIAgent orchestrates:
   - Condition: user_override > metadata > folder_name > AI-detected > DEFAULT_CONDITION
   - AI: Gemini vision analysis via `AI_MODEL_NAME` in `core/constants.py` (currently `gemini-3-flash-preview`; pricing/grounding uses `AI_PRICING_MODEL`), cached in ai_json to avoid re-analysis
   - Category: CategoryMapper → taxonomy.py `get_safe_category()` (hardware guards with context awareness) → eBay Taxonomy API (fallback: 170599)
   - Price: PricingEngine cascade: ISBN → MPN → alt part numbers → keywords → research market price → Gemini grounding → AI estimate. Rarity-aware (75th percentile for rare items). All paths add `ESTIMATED_SHIPPING_COST` buffer ($6.50 default) for free shipping.
   - Images: upload to eBay EPS (max 12)
   - Template: TemplateManager renders inline-styled HTML (eBay strips `<style>`/`<head>` on mobile)
   - eBay: Trading API `AddFixedPriceItem` (XML) → active or scheduled listing
3. Real-time status via Socket.IO → frontend updates via useJobSync

## Rate Limits

- **Gemini**: `GEMINI_RPM_LIMIT` env var, default 60 (paid tier; set 2 for free tier) — token bucket, burst min(5, RPM)
- **eBay**: 5 burst, 2 tokens/sec refill — enforced in ebay_request() wrapper

## Environment (.env)

Required: `EBAY_APP_ID`, `EBAY_CERT_ID`, `EBAY_USER_TOKEN`, `GOOGLE_API_KEY`
Business policies: `EBAY_FULFILLMENT_POLICY`, `EBAY_PAYMENT_POLICY`, `EBAY_RETURN_POLICY`, `EBAY_MERCHANT_LOCATION`
Optional: `DEFAULT_CONDITION` (USED_EXCELLENT), `DEFAULT_PRICE` (29.99), `AUTO_PUBLISH` (false), `CONFIDENCE_THRESHOLD` (85), `PORT` (5000), `ESTIMATED_SHIPPING_COST` (6.50 — baked into listing price since fulfillment policy is free shipping)
Pricing/guardrails (optional): `ACTIVE_TO_SOLD_FACTOR` (0.87, settings-editable), `PRICE_AGREEMENT_RATIO` (1.6 — comps-vs-AI conflict threshold), `PRICE_REVIEW_THRESHOLD` (150.0), `PRICE_COMP_MULTIPLE` (3.0), `DUP_HASH_DISTANCE` (6), `DUP_LOOKBACK_DAYS` (30)
Best Offer / discovery (optional): `BEST_OFFER_ENABLED` (true), `BEST_OFFER_AUTO_ACCEPT_PCT` (90), `BEST_OFFER_AUTO_DECLINE_PCT` (60), `PRICE_DISCOVERY_ENABLED` (true), `PRICE_DISCOVERY_MARKUP_PCT` (25), `PRICE_DISCOVERY_DECLINE_PCT` (50)
Autopilot (optional): `OFFERS_ENABLED` (true), `OFFER_DISCOUNT_PCT` (10), `OFFER_MIN_WATCHERS` (1), `MARKDOWN_ENABLED` (true), `MARKDOWN_AFTER_DAYS` (14), `MARKDOWN_STEP_PCT` (5), `MARKDOWN_FLOOR_PCT` (70), `OFFERS_MARKDOWNS_DRY_RUN` (**true** — flip after reviewing digests), `DISCOVERY_MARKDOWN_AFTER_DAYS` (7), `DISCOVERY_MARKDOWN_STEP_PCT` (10), `DISCOVERY_MARKDOWN_FLOOR_PCT` (40), `AUTOPILOT_RUN_HOUR` (9), `RELIST_ENABLED` (true), `RELIST_MAX_TIMES` (3)
Notifications (optional): `WHATSAPP_NOTIFY_CHAT_ID` (empty — owner chat for price-review texts + queue digests on non-WhatsApp jobs)
Promoted Listings (optional): `PROMOTED_LISTINGS_ENABLED` (false), `PROMOTED_LISTINGS_AD_RATE` (5.0)
Security/reliability (optional): `API_ACCESS_TOKEN` (unset = remote API access denied; see Gotchas), `AI_ANALYSIS_TIMEOUT` (300 — outer seconds cap on the AI phase so a hung Gemini call can't block the queue worker)
OAuth scopes (`auth.py` SCOPES + `token_manager.py` EBAY_SCOPES) now include `sell.marketing`.

Settings UI writes directly to .env via SettingsManager singleton.

## Ports

- Production: Flask on 5000, serves API + React SPA at /app/
- Dev: Vite on 5175 proxies /api to 127.0.0.1:5000

## Testing

```bash
pytest tests/unit/ -v               # Unit tests (244 tests)
pytest tests/integration/ -v        # Integration tests (need .env credentials + eBay sandbox)
pytest tests/unit/test_validation.py  # Single file
python tests/manual/manual_test_api.py  # Manual integration test
python tests/manual/manual_test_e2e.py  # Full pipeline test
```

Test conventions: `test_*.py` files, `Test*` classes, `test_*` functions.

### Integration test fixtures
Real product images in `tests/fixtures/images/` for full pipeline testing:
- `boombox/` — Aiwa CSD-ES227 stereo (electronics category)
- `cookbook/` — Coffee cookbook (books/ISBN category)
- `tesla-jacket/` — Tesla branded jacket (clothing/apparel category)

`test_full_pipeline.py` runs complete AI→category→pricing→eBay flow. `test_live_pipeline.py` does quick API-only listing+cleanup.

### Playwright (browser testing)
```bash
# Uses playwright-skill at ~/.claude/skills/playwright-skill/
# Write test scripts to /tmp, execute via skill runner:
cd ~/.claude/skills/playwright-skill && node run.js /tmp/playwright-test-*.js
```
- Vite dev server must be running on 5175, Flask backend on 5000
- Use `headless: false` for visible browser, `slowMo: 150` for debugging
- Parameterize URL as `const TARGET_URL = 'http://localhost:5175'`

## Gotchas

- **API auth: loopback trusted, remote needs X-API-Key** — `api/__init__.py` `before_request` allows 127.0.0.1/::1 (desktop browser, Hermes bridge, supervisor) without a key; any other caller (LAN/Tailscale phone) must send `X-API-Key` matching `API_ACCESS_TOKEN` (read live from SettingsManager, so saving it in Settings applies without restart; unset = remote denied 401). Exempt: `/api/system/health` and GET `/api/job/<id>/image/<file>` (`<img>` tags can't send headers; path-traversal-guarded instead). Frontend `apiFetch` stores the key in localStorage (`dc-api-key`) and prompts once on 401. Socket.IO events are NOT gated (read-only job status).
- **Masked secrets never round-trip** — GET `/api/settings` masks sensitive values as `••••` (full mask, no suffix). POST `/api/settings` drops any value starting with `••••`, so the Settings page posting back untouched masked fields can't overwrite real secrets in `.env`.
- **`.env` writes are atomic** — `settings_manager.save()` and `auth.save_tokens()` write `<name>.tmp` then `os.replace()`. Never revert to plain `open('w')`: a crash mid-write would truncate every credential.
- **Frontend lib/ files** — `src/lib/api.ts`, `utils.ts`, `sanitizer.ts`, `pwa.ts` are imported everywhere. If missing, nothing compiles.
- **Worktree `.env` shadowing** — Never create `.env` in a worktree. `load_dotenv_manually()` walks up parent dirs to find the main project's `.env` automatically. A worktree `.env` will shadow it and cause missing-policy errors.
- **eBay token refresh** — Background thread. Also auto-refreshes on 401 in ebay_request()
- **AI data caching** — If job.ai_data already has `listing` key, AI analysis is skipped (uses cached). Clear ai_json to force re-analysis
- **Title max 80 chars** — eBay enforced, validated in both frontend and backend
- **Aspect values max 65 chars** — Truncated silently in pipeline
- **Browse API uses client credentials** not user token (different auth flow in browse.py)
- **Trading API XML** — Used for ALL new listings (`AddFixedPriceItem`). Also used as read fallback (`GetSellerList`) when Inventory API returns 0 items. Inventory API still used for existing listing management (update, withdraw, publish).
- **CONDITION_ID_MAP** — Maps condition enum strings to numeric eBay condition IDs (needed for Trading API XML)
- **Config .env loading** — `backend/config.py` loads `.env` via `load_dotenv_manually()` which walks up all parent directories from `BASE_DIR` until it finds a `.env` file. This supports git worktrees nested several levels deep. Without this, `os.environ` / `app.config` won't have eBay policies and ALL listings fail with missing return policy errors.
- **eBay description template** — `templates/ebay_master.html` uses inline styles ONLY. eBay strips `<head>`, `<style>`, and `<link>` tags on mobile. Never use CSS classes or `<style>` blocks.
- **Category taxonomy guards** — `taxonomy.py` has keyword guards for printer parts (fuser, drum, hardware). The `drum` guard requires printer context (laser/printer/toner). A `non_hardware_context` word list prevents board games, toys, etc. from hitting the printer guard. If items get wrong categories, check `get_safe_category()`.
- **Windows cp1252 emoji encoding** — Logger calls with emoji characters fail on Windows console (cp1252 codec). Emojis in log messages cause `UnicodeEncodeError` but don't crash the pipeline — they're cosmetic logging errors only.
- **Free shipping pricing** — Fulfillment policy uses free shipping. `ESTIMATED_SHIPPING_COST` (default $6.50) is added to suggested price so seller margin isn't eaten by shipping. The buffer is applied in `pricing_engine.py` after the condition multiplier.
- **Git worktrees** — `.env` is not tracked by git, but `load_dotenv_manually()` now walks up parent directories to find it. Worktrees should work for development, but note that `data/commander.db` is also not shared — each worktree gets its own database.
- **Queue API routes** — Queue control is at `/api/start`, `/api/pause`, `/api/skip` (no `/queue/` prefix) because `queue_bp` is registered with `url_prefix=''`.
- **System API routes** — System endpoints are at `/api/system/health`, `/api/system/restart`, `/api/system/clear-taxonomy-cache` because `system_bp` is registered with `url_prefix='/system'`.
- **`ebay_aspect_schema` not `ebay_required_aspects`** — The old key was replaced. `ai_data['ebay_aspect_schema']` is the full required+optional aspect list. Frontend `JobDetails` type uses `ebay_aspect_schema`. Old jobs may have stale `ebay_required_aspects` key.
- **Claude Code hooks active** — `.claude/settings.json` has PreToolUse hook blocking `.env` edits and PostToolUse hook running ESLint on frontend files. `.env` must be edited through SettingsManager/API, never directly.
- **rembg dependency** — `requirements.txt` includes `rembg`. First run downloads ~170MB ONNX model. If image processing is slow or fails on a new machine, this is likely why.
- **Serena memories** — 4 project memories exist (`architecture`, `debugging-patterns`, `api-routes`, `frontend-patterns`). Read these at session start for instant context.
- **Research data in descriptions** — `processor_service.py` interpolates web research specs into HTML description via `{research_specs_section}` placeholder. All research data is `html.escape()`'d to prevent XSS.
- **Condition ID validation** — `taxonomy.py:validate_condition_for_category()` checks condition IDs against eBay category policies. Falls back through condition hierarchy if original ID is invalid for the category.
- **Results logger** — `results_logger.py` appends JSONL to `data/listing_results.jsonl`. NOT a test framework — it's for tracking real listing outcomes over time to improve AI quality. Use `get_results(last_n=10)` for recent entries.
- **SAFE_DEFAULT_ASPECTS** — Set in `processor_service.py`: `{Brand, MPN, Type, Model, UPC, EAN, Country/Region of Manufacture, California Prop 65 Warning}`. These get auto-filled with "Does Not Apply" when missing. Category-specific required aspects (like Size, Color) route job to review instead.
- **eBay OAuth re-consent is manual (no web callback)** — to add a scope (e.g. `sell.marketing`): add it to `auth.py` SCOPES + `token_manager.py` EBAY_SCOPES, then re-consent: `eBayOAuth(use_sandbox=False).get_authorization_url()` → user opens it + clicks Agree → copy the `code` from the redirect → `exchange_code_for_token(code)`. **Critical:** also call `token_manager.store_tokens(access, refresh)` — `save_tokens()` only writes `.env`, but the running app reads the access token from the SQLite DB. A token *refresh* keeps the OLD scope set; a NEW scope requires a fresh consent. `tools/exchange_token.py` helps.
- **DC restart (supervisor)** — `backend/run_service.py` is a supervisor that launches `wsgi_service.py` as a disposable child and sets `DC_SUPERVISED=1`. `POST /api/system/restart` now exits the child with code **42**; the supervisor relaunches it into a freshly released port 5000 (child death closes the eventlet listener FD *before* respawn — no bind race). Exit-code contract: `42`=restart, `0`=stop, other=crash→auto-relaunch (crash-loop guard: >3 crashes/60s gives up). **Launch detached:** `Start-Process pythonw backend\run_service.py` (not `wsgi_service.py`). If launched *without* the supervisor (e.g. `python backend/wsgi.py`), `/restart` returns **409** and does nothing — restart manually. The old `os.execv` approach left port 5000 unbound on Windows and is gone. Still required after backend changes (no hot-reload), but now a one-click restart instead of a manual PID kill. **Autostart:** `scripts/register-service.ps1` installs a logon-triggered launcher (Scheduled Task with admin, Startup-folder shortcut → `start-background.ps1` without). All three launch paths (`run-backend.bat` template, `start-background.ps1`, the script's immediate-start) now launch `run_service.py` — they previously launched `wsgi.py`/`wsgi_service.py` directly, which is why the backend kept ending up un-supervised with `/restart` 409ing. If editing these scripts, never point them back at `wsgi*.py`. **Phone HTTPS:** served by `tailscale serve --bg 5000` (config persists inside tailscaled across reboots) at `https://tuf-2.taile466a6.ts.net` — NOT Caddy; Windows Firewall auto-created block rules for caddy.exe, so inbound 443 to Caddy is unreachable from other devices. `register-service.ps1 -Https` still writes the Caddy setup but `start-background.ps1` deliberately doesn't launch it.
- **Phone URL dead? Check Tailscale login first** — `tailscale status` showing "logged out"/"NoState" means the daemon lost its session (happened 2026-07-17). Serve config persists and auto-restores after re-login (tray icon → Log in, then verify `tailscale serve status`). LAN fallback while down: `http://192.168.1.142:5000/app/` — works for capture (OS camera via file input) but NOT the barcode scanner (getUserMedia needs HTTPS). Phone must also have its Tailscale toggle ON.
- **Tests need Python 3.12** — use `"C:\Program Files\Python312\python.exe" -m pytest tests/unit -v`. The bare `python`/`py` launchers may resolve to a 3.13 install missing project deps (Flask etc.).
- **Listing edits: price/qty revise + end** — `trading.py:revise_fixed_price_item(item_id, price, qty)` (ReviseFixedPriceItem) now does in-place **price/qty** changes on live Trading-API listings, exposed at `POST /api/listings/<itemId>/price`. **Title/specifics still have no revise** — end and re-capture for those (guardrails clean it on re-list). Also `POST /api/listings/<itemId>/end` (EndFixedPriceItem) and `POST /api/listings/<itemId>/promote` (Marketing API). `/api/jobs/<id>/cancel` ends the eBay listing + removes the job; `/api/jobs/bulk-delete` removes the job record without touching eBay.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`Lilbuff3/eBay_Draft_Commander`, via the `gh` CLI); external PRs are NOT a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix (stock `wontfix` label reused). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root (created lazily). See `docs/agents/domain.md`.
  - **Eventlet Migration Decision** — Eventlet is officially dead (last release early 2024, Python 3.12+ issues) and the backend relies on it for SocketIO. We cannot migrate today as it requires switching to gevent or moving to FastAPI. TODO: Migrate to gevent/asyncio before Python 3.13 becomes mandatory.
