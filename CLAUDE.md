# eBay Draft Commander

AI-powered eBay listing automation. Flask backend + React TypeScript frontend + Electron desktop packaging.

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
python backend/wsgi.py                    # Start server (port 5000)
pytest tests/ -v                          # Run tests
python manage.py update_policies          # Fetch eBay policies to .env
python manage.py fix_publish <offer_id>   # Fix policies and publish offer

# Frontend
cd frontend && npm install
npm run dev                               # Vite dev server (port 5175, proxies /api to 5000)
npm run build                             # Build to ../static/app/
npm run test                              # Vitest
npm run electron:dev                      # Electron + Vite dev
npm run electron:build                    # Package Electron distributable

# Full stack dev
# Terminal 1: python backend/wsgi.py
# Terminal 2: cd frontend && npm run dev
```

## Architecture

```
backend/                    Flask app factory
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
        system_api.py       /api/system (health, token status)
        helpers.py          Shared utilities for API routes
      ui.py                 Serves React SPA at /app/, redirects / to /app/
    core/
      constants.py          CONDITION_MAP, CONDITION_ID_MAP, rate limits, model names
      database.py           SQLAlchemy models (JobModel, TemplateModel, OrphanedMedia, AppToken)
      models.py             InternalListing dataclass (adapter pattern)
      settings_manager.py   .env read/write singleton
      rate_limiter.py       Token-bucket (gemini: 2 RPM, ebay: 5 burst)
      token_manager.py      Centralized eBay access token management (SQLite-backed)
      validator.py          Input validation (price, title, ISBN, paths)
      paths.py              Cross-platform path resolution (dev vs frozen)
      exceptions.py         Custom exception hierarchy
      logger.py             Logging configuration
      prompts.py            AI prompt templates
    services/
      queue_service.py      Job lifecycle, background threads, Socket.IO events
      listing_ai_agent.py   AI-powered listing creation orchestrator
      scanner_service.py    Inbox folder scanning and detection
      ai_analyzer.py        Google Gemini vision + research
      ai_price.py           AI-assisted pricing
      pricing_engine.py     Market research pricing with fallback chain
      ebay_service.py       eBay API facade
      category_mapper.py    eBay category taxonomy mapping
      template_manager.py   HTML description template rendering
      image_processor.py    Image processing and optimization
      image_service.py      Image upload coordination
      isbn_scanner.py       ISBN barcode detection
      book_service.py       Book-specific metadata lookup
      item_specifics_mapper.py  eBay item specifics mapping
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
frontend/                   React 18 + Vite + TypeScript
  src/
    App.tsx                 Tab-based navigation via activeTab state, global layout
    store/
      useCommanderStore.ts  Single Zustand store (jobs, queue, settings, UI state)
    hooks/
      useJobSync.ts         Socket.IO real-time job synchronization
      useHaptics.ts         Mobile haptic feedback
      usePullToRefresh.ts   Pull-to-refresh gesture (currently disabled)
    lib/
      api.ts                Typed fetch wrapper (apiFetch<T>)
      utils.ts              Shared utilities
      sanitizer.ts          Input sanitization
      pwa.ts                PWA install/update logic
    pages/                  Dashboard, Settings, BatchScan
    components/             30+ components
      ui/                   shadcn/Radix primitives
      item-detail/          Item description/specifics/schedule cards
      listings/             Bulk actions, edit dialog, media manager
```

## Key Patterns

- **Tab-based navigation** — `activeTab` state in `useCommanderStore`, persisted to localStorage. No react-router.
- **Zustand for state** — Single store (`useCommanderStore.ts`) manages jobs, queue status, settings, selected job, UI state. Accessed via selectors.
- **Typed HTTP client** — `apiFetch<T>()` in `src/lib/api.ts` wraps fetch with generics and error handling.
- **Socket.IO events**: `job_added`, `job_update`, `job_log` — emitted by QueueService, consumed via `useJobSync` hook.
- **Condition priority chain** — user_override > metadata > folder_name (CONDITION_MAP) > **AI-detected** > DEFAULT_CONDITION. AI refinement in `_refine_condition_from_ai()` only fires when no explicit override exists.
- **SKU format**: `DC-{8 uppercase hex}` generated in listing pipeline
- **Listing creation uses Trading API** — `AddFixedPriceItem` (XML), not Inventory API. Supports `ScheduleTime` for scheduled listings.
- **Scheduled listings** — Dashboard has datetime picker; `scheduled_time` stored on job, passed through to Trading API `ScheduleTime` field.
- **Job statuses**: pending, processing, completed, failed, paused, skipped, scheduled
- **API is modular** — `blueprints/api/` is a package with 7 sub-modules, not a single file.

## Database

SQLite at `data/commander.db`. ORM: SQLAlchemy. WAL mode enabled.

- **`jobs`** table (JobModel) — id (8-char hex PK), folder_path, status, scheduled_time, AI data + user overrides stored as JSON text columns (ai_json, item_specifics_json, metadata_json, timing_json)
- **`templates`** table (TemplateModel) — name (unique), data_json, use_count
- **`orphaned_media`** table — Tracks uploaded images from failed listings for cleanup
- **`app_tokens`** table — eBay access token persistence

SQLite pragmas: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`

## Processing Pipeline

1. Images in `inbox/` → ScannerService detects → creates job
2. ListingAIAgent orchestrates:
   - Condition: user_override > metadata > folder_name > AI-detected > DEFAULT_CONDITION
   - AI: Gemini 2.0 Flash vision analysis (cached in ai_json to avoid re-analysis)
   - Category: CategoryMapper → taxonomy.py `get_safe_category()` (hardware guards with context awareness) → eBay Taxonomy API (fallback: 170599)
   - Price: PricingEngine cascade: ISBN search → keyword search → Gemini grounding → AI estimate. All paths add `ESTIMATED_SHIPPING_COST` buffer ($6.50 default) for free shipping.
   - Images: upload to eBay EPS (max 12)
   - Template: TemplateManager renders inline-styled HTML (eBay strips `<style>`/`<head>` on mobile)
   - eBay: Trading API `AddFixedPriceItem` (XML) → active or scheduled listing
3. Real-time status via Socket.IO → frontend updates via useJobSync

## Rate Limits

- **Gemini**: 2 RPM (free tier) — token bucket 1 capacity, refill 1/30s
- **eBay**: 5 burst, 2 tokens/sec refill — enforced in ebay_request() wrapper

## Environment (.env)

Required: `EBAY_APP_ID`, `EBAY_CERT_ID`, `EBAY_USER_TOKEN`, `GOOGLE_API_KEY`
Business policies: `EBAY_FULFILLMENT_POLICY`, `EBAY_PAYMENT_POLICY`, `EBAY_RETURN_POLICY`, `EBAY_MERCHANT_LOCATION`
Optional: `DEFAULT_CONDITION` (USED_EXCELLENT), `DEFAULT_PRICE` (29.99), `AUTO_PUBLISH` (false), `CONFIDENCE_THRESHOLD` (85), `PORT` (5000), `ESTIMATED_SHIPPING_COST` (6.50 — baked into listing price since fulfillment policy is free shipping)

Settings UI writes directly to .env via SettingsManager singleton.

## Ports

- Production: Flask on 5000, serves API + React SPA at /app/
- Dev: Vite on 5175 proxies /api to 127.0.0.1:5000

## Testing

```bash
pytest tests/ -v                    # Unit tests
pytest tests/test_validation.py     # Single file
python tests/manual_test_api.py     # Integration test
python tests/manual_test_e2e.py     # Full pipeline test
```

Test conventions: `test_*.py` files, `Test*` classes, `test_*` functions.

## Gotchas

- **Frontend lib/ files** — `src/lib/api.ts`, `utils.ts`, `sanitizer.ts`, `pwa.ts` are imported everywhere. If missing, nothing compiles.
- **Frozen mode paths** — In PyInstaller builds, data goes to `%LOCALAPPDATA%/eBayDraftCommander/` not project root
- **eBay token refresh** — Background thread. Also auto-refreshes on 401 in ebay_request()
- **AI data caching** — If job.ai_data already has `listing` key, AI analysis is skipped (uses cached). Clear ai_json to force re-analysis
- **Title max 80 chars** — eBay enforced, validated in both frontend and backend
- **Aspect values max 65 chars** — Truncated silently in pipeline
- **Browse API uses client credentials** not user token (different auth flow in browse.py)
- **Trading API XML** — Used for ALL new listings (`AddFixedPriceItem`). Also used as read fallback (`GetSellerList`) when Inventory API returns 0 items. Inventory API still used for existing listing management (update, withdraw, publish).
- **CONDITION_ID_MAP** — Maps condition enum strings to numeric eBay condition IDs (needed for Trading API XML)
- **@supabase/supabase-js** in package.json but unused in source — safe to remove
- **Config .env loading** — `backend/config.py` loads `.env` via `load_dotenv_manually()` in BOTH dev and frozen mode. Without this, `os.environ` / `app.config` won't have eBay policies and ALL listings fail with missing return policy errors.
- **eBay description template** — `templates/ebay_master.html` uses inline styles ONLY. eBay strips `<head>`, `<style>`, and `<link>` tags on mobile. Never use CSS classes or `<style>` blocks.
- **Category taxonomy guards** — `taxonomy.py` has keyword guards for printer parts (fuser, drum, hardware). The `drum` guard requires printer context (laser/printer/toner). A `non_hardware_context` word list prevents board games, toys, etc. from hitting the printer guard. If items get wrong categories, check `get_safe_category()`.
- **Windows cp1252 emoji encoding** — Logger calls with emoji characters fail on Windows console (cp1252 codec). Emojis in log messages cause `UnicodeEncodeError` but don't crash the pipeline — they're cosmetic logging errors only.
- **Free shipping pricing** — Fulfillment policy uses free shipping. `ESTIMATED_SHIPPING_COST` (default $6.50) is added to suggested price so seller margin isn't eaten by shipping. The buffer is applied in `pricing_engine.py` after the condition multiplier.
- **Git worktrees** — Avoid for this project. Worktrees don't share `.env` (not tracked by git), causing policy loading failures. Use feature branches on the main clone instead.
- **Queue API routes** — Queue control is at `/api/start`, `/api/pause`, `/api/skip` (no `/queue/` prefix) because `queue_bp` is registered with `url_prefix=''`.
