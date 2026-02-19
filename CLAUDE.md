# eBay Draft Commander

AI-powered eBay listing automation. Flask backend + React TypeScript frontend + Electron desktop packaging.

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
npm run dev                               # Vite dev server (port 5175, proxies /api to 5001)
npm run build                             # Build to ../static/app/
npm run test                              # Vitest
npm run electron:dev                      # Electron + Vite dev
npm run electron:build                    # Package Electron distributable

# Full stack dev
# Terminal 1: python backend/wsgi.py (or set PORT=5001)
# Terminal 2: cd frontend && npm run dev
```

## Architecture

```
backend/                    Flask app factory
  app/
    __init__.py             create_app(), SocketIO singleton
    blueprints/
      api.py                All /api/* REST endpoints
      ui.py                 Serves React SPA at /app/, legacy templates at /
    core/
      constants.py          CONDITION_MAP, CONDITION_ID_MAP, rate limits, model names
      database.py           SQLAlchemy models (JobModel, TemplateModel)
      settings_manager.py   .env read/write singleton
      rate_limiter.py       Token-bucket (gemini: 2 RPM, ebay: 5 burst)
      validator.py          Input validation (price, title, ISBN, paths)
      paths.py              Cross-platform path resolution (dev vs frozen)
    services/
      processor_service.py  Main pipeline orchestrator
      queue_manager.py      Job lifecycle, background threads, Socket.IO events
      ai_analyzer.py        Google Gemini vision + research
      pricing_engine.py     Market research pricing with fallback chain
      ebay_service.py       eBay API facade
      ebay/                 eBay REST/XML API modules (auth, inventory, media, etc.)
frontend/                   React 18 + Vite + TypeScript
  src/
    App.tsx                 Tab-based navigation (no react-router), global state
    pages/                  Dashboard, Settings, BatchScan
    components/             25+ components, ui/ has shadcn/Radix primitives
    hooks/                  usePullToRefresh (currently disabled)
    lib/                    api.ts, utils.ts, stages.ts, sanitizer.ts
```

## Key Patterns

- **No react-router** — Navigation is tab-based via `activeTab` state in App.tsx persisted to localStorage
- **No state management library** — All state lifted to App.tsx, passed via props. No Context, Redux, or Zustand
- **No centralized HTTP client** — Frontend uses raw `fetch()`. API abstractions in `src/lib/api.ts`
- **Socket.IO events**: `job_added`, `job_update`, `job_log` — emitted by QueueManager, consumed in App.tsx
- **Condition from folder structure** — `inbox/{condition_folder}/{item_folder}/` maps via CONDITION_MAP
- **SKU format**: `DC-{8 uppercase hex}` generated in processor_service.py
- **Listing creation uses Trading API** — `AddFixedPriceItem` (XML), not Inventory API. Supports `ScheduleTime` for scheduled listings.
- **Scheduled listings** — Dashboard has datetime picker; `scheduled_time` stored on QueueJob, passed through to Trading API `ScheduleTime` field. Items appear in eBay Seller Hub > Scheduled.
- **Job statuses**: pending, processing, completed, failed, paused, skipped, **scheduled**

## Database

SQLite at `data/commander.db`. ORM: SQLAlchemy.

- **`jobs`** table (JobModel) — id (8-char hex PK), folder_path, status (pending/processing/completed/failed/paused/skipped/scheduled), scheduled_time, AI data + user overrides stored as JSON text columns (ai_json, item_specifics_json, metadata_json, timing_json)
- **`templates`** table (TemplateModel) — name (unique), data_json, use_count

## Processing Pipeline

1. Images in `inbox/` → QueueManager detects (10s poll) → creates QueueJob
2. ProcessorService.create_listing() orchestrates:
   - Condition: user_override > metadata > folder_name > DEFAULT_CONDITION
   - AI: Gemini 2.0 Flash vision analysis (cached in ai_json to avoid re-analysis)
   - Category: CategoryMapper → eBay Taxonomy API (fallback: 170599)
   - Price: PricingEngine cascade: ISBN search → keyword search → Gemini grounding → AI estimate
   - Images: upload to eBay EPS (max 12)
   - Template: TemplateManager renders HTML description
   - eBay: Trading API `AddFixedPriceItem` (XML) → active or scheduled listing
3. Real-time status via Socket.IO → frontend updates

## Rate Limits

- **Gemini**: 2 RPM (free tier) — token bucket 1 capacity, refill 1/30s
- **eBay**: 5 burst, 2 tokens/sec refill — enforced in ebay_request() wrapper

## Environment (.env)

Required: `EBAY_APP_ID`, `EBAY_CERT_ID`, `EBAY_USER_TOKEN`, `GOOGLE_API_KEY`
Business policies: `EBAY_FULFILLMENT_POLICY`, `EBAY_PAYMENT_POLICY`, `EBAY_RETURN_POLICY`, `EBAY_MERCHANT_LOCATION`
Optional: `DEFAULT_CONDITION` (USED_EXCELLENT), `DEFAULT_PRICE` (29.99), `AUTO_PUBLISH` (false), `CONFIDENCE_THRESHOLD` (85), `PORT` (5000)

Settings UI writes directly to .env via SettingsManager singleton.

## Ports

- Production: Flask on 5000, serves API + React SPA at /app/
- Dev: Vite on 5175 proxies /api to 127.0.0.1:5001

## Testing

```bash
pytest tests/ -v                    # Unit tests (19 files)
pytest tests/test_validation.py     # Single file
python tests/manual_test_api.py     # Integration test
python tests/manual_test_e2e.py     # Full pipeline test
```

Test conventions: `test_*.py` files, `Test*` classes, `test_*` functions.

## Gotchas

- **Frontend lib/ files** — `src/lib/api.ts`, `utils.ts`, `stages.ts`, `sanitizer.ts` are imported everywhere. If missing, nothing compiles.
- **Frozen mode paths** — In PyInstaller builds, data goes to `%LOCALAPPDATA%/eBayDraftCommander/` not project root
- **eBay token refresh** — Background thread every 60min. Also auto-refreshes on 401 in ebay_request()
- **AI data caching** — If job.ai_data already has `listing` key, AI analysis is skipped (uses cached). Clear ai_json to force re-analysis
- **Title max 80 chars** — eBay enforced, validated in both frontend and backend
- **Aspect values max 65 chars** — Truncated silently in processor_service
- **Browse API uses client credentials** not user token (different auth flow in browse.py)
- **Trading API XML** — Used for ALL new listings (`AddFixedPriceItem`). Also used as read fallback (`GetSellerList`) when Inventory API returns 0 items. Inventory API still used for existing listing management (update, withdraw, publish).
- **CONDITION_ID_MAP** — Maps condition enum strings to numeric eBay condition IDs (needed for Trading API XML)
- **Hardcoded localhost:5000** in ScannerListener.tsx and BatchScan.tsx — should use /api proxy
- **@supabase/supabase-js** in package.json but unused in source
