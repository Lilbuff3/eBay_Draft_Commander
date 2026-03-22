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
python backend/wsgi.py                    # Start server (port 5000)
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
      paths.py              Cross-platform path resolution
      exceptions.py         Custom exception hierarchy
      logger.py             Logging configuration
      prompts.py            AI prompt templates
      results_logger.py     JSONL listing outcome logger (data/listing_results.jsonl)
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
      image_processor.py    Image processing, background removal, upload
      processor_service.py  Main processing orchestrator (AI, category, pricing, upload)
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
- **Image reordering** — `ImageGallery` uses `@dnd-kit` drag-and-drop. `ordered_images` stored in `job_metadata`, respected by `image_processor.upload_images()`. First image = eBay cover photo.
- **Aspect schema** — `ebay_aspect_schema` (not old `ebay_required_aspects`) returns full required+optional aspects with `isRequired` flag. Dynamic refresh via `/api/lookup/category/<id>/aspects`. Fuzzy value matching in `processor_service._validate_and_enrich_specifics()`.
- **Background removal** — `image_processor.remove_background_and_square()` uses `rembg` + Pillow. Composites subject onto 2000x2000 white JPEG canvas. Originals preserved as `.orig` files.
- **3-phase AI pipeline** — Phase 1: Gemini vision analysis. Phase 2: Gemini with Google Search grounding (web research for specs, pricing, availability). Phase 3: aspect mapping with research-enriched prompts.
- **Smart title selection** — `listing_ai_agent.py` picks `max([seo_title, suggested_title], key=len)` — longer title = more descriptive for eBay SEO.
- **Required aspects guard** — `processor_service.py` validates required aspects before eBay submission. Auto-fills generic aspects (Brand, MPN, Type, UPC, etc.) with "Does Not Apply". Category-specific missing aspects route job to review instead of failing.
- **Results logging** — `results_logger.py` writes JSONL to `data/listing_results.jsonl`. Each record captures title, price, category, condition, comps, source, and outcome. Use `get_results()` and `compare_last_runs()` for analysis.
- **Pricing cascade (expanded)** — ISBN → MPN → Alt part numbers → Keywords → Research market price → Gemini grounding → AI estimate. Rarity-aware: rare/very_rare items use 75th percentile instead of median. Comps and reasoning persisted to job metadata.

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
   - Price: PricingEngine cascade: ISBN → MPN → alt part numbers → keywords → research market price → Gemini grounding → AI estimate. Rarity-aware (75th percentile for rare items). All paths add `ESTIMATED_SHIPPING_COST` buffer ($6.50 default) for free shipping.
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
