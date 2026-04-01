<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# backend/app/services/ebay

## Purpose
eBay API integration modules wrapping production (Trading, Inventory, Browse, Taxonomy, Policies, Analytics, Media) and sandbox APIs. Each module handles authentication, request/response parsing, rate limiting, error handling, and caching. Designed for consumption by higher-level services (`ebay_service.py`, `pricing_engine.py`, `category_mapper.py`, etc.).

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker |
| `auth.py` | eBay OAuth 2.0 — user authorization flow, token refresh, thread-safe token caching, production + sandbox support |
| `trading.py` | Trading API (XML) — canonical for new listings. `AddFixedPriceItem` (create with `ScheduleTime`), `GetSellerList` (active listings), `EndFixedPriceItem` (end listings), token refresh on 401 |
| `inventory.py` | Inventory API (REST) — modern listing management. Fetch active, update, out-of-stock control, graceful 401 fallback |
| `browse.py` | Browse API (REST, client credentials) — read-only market research. Search, price history, condition metadata |
| `media.py` | EPS Media Upload API (REST) — upload listing images, returns URLs for Trading API. Max 12 images per listing |
| `taxonomy.py` | Taxonomy API (REST) — category suggestions, item aspects schema, condition ID validation. Two-tier cache (LRU + SQLite), 48-hour TTL |
| `policies.py` | Business Policies API (REST) — fulfillment, payment, return policy IDs. Shared helpers: `_get_headers()`, `_refresh_token_if_needed()`, `ebay_request()` wrapper |
| `researcher.py` | Market research orchestrator — Browse API search + Gemini grounding, rarity detection (< 5 sold = rare) |
| `analytics.py` | Seller Analytics API (REST) — active listings, revenue, category breakdown for dashboard |
| `adapters.py` | Data mappers — `TradingAPIAdapter` (InternalListing → Trading XML), `InventoryAPIAdapter` (InternalListing → Inventory JSON), `CONDITION_ID_MAP` |

## For AI Agents

### Working In This Directory

**Add new API integration:**
1. Create module (e.g., `fulfillment.py`)
2. Import shared helpers from `policies.py`: `ebay_request()`, `_get_headers()`, `_refresh_token_if_needed()`
3. Implement request/response parsing
4. Add caching if needed (follow taxonomy.py two-tier pattern)

**Modify existing integration:**
- Update appropriate module
- Auth changes → `auth.py`
- Request/response format → `trading.py`, `inventory.py`, etc.
- Token refresh handled by `_refresh_token_if_needed()` helper

**Add caching:**
- Two-tier pattern: in-memory LRU (OrderedDict, fast) + SQLite fallback (persistent)
- Use `_normalize_query()` for cache key generation
- Set TTL and check timestamp on retrieval

**Handle token refresh:**
- Call `_refresh_token_if_needed()` from `policies.py` before requests
- Or manually call `get_token_manager().refresh_if_needed()`
- 401 responses trigger auto-refresh via `ebay_request()` wrapper

**Rate limiting:**
- All eBay requests → `ebay_request()` wrapper enforces token-bucket (5 burst, 2/sec refill)
- Gemini requests have separate 2 RPM limit in `rate_limiter.py`

### Common Patterns

**Request wrappers:**
- `ebay_request(method, url, ...)` handles auth headers, 401 refresh, retries, rate limiting
- Use instead of raw `requests.post()`

**Error handling:**
- Trading API → XML errors, REST APIs → JSON errors
- Parse and raise exceptions or return error dicts
- Don't fail silently — log warnings and propagate upstream

**Caching strategy:**
- In-memory first (fast, no I/O): `OrderedDict` with `maxlen` for LRU (e.g., 500 entries)
- SQLite fallback (persistent): `SELECT data FROM cache WHERE key=? AND timestamp > ?`
- Manual invalidation routes: `/system/clear-taxonomy-cache`

**Condition ID mapping:**
- Trading API: numeric IDs (1000=New, 3000=Used)
- Inventory API: strings (NEW, USED_EXCELLENT)
- Map via `CONDITION_ID_MAP` in `adapters.py`

**XML handling:**
- Trading API requires XML escaping for titles, descriptions, specifics
- Use `xml.sax.saxutils.escape()` for safety (prevents injection)

**Scheduled listings:**
- `ScheduleTime` field in `AddFixedPriceItem` accepts ISO 8601 datetime
- Parser in `trading.py` handles both datetime objects and ISO strings

**Image limits:**
- Max 12 images per listing (enforced in `media.py`)
- Reorder via `ordered_images` in job metadata before upload

**Graceful degradation:**
- When eBay API unreachable (auth fails), return empty results or offline fallback
- Example: `inventory.py` 401 handling returns empty list instead of crashing

### Dependencies

**Internal:**
- `backend.app.core.logger` — Module-level logging
- `backend.app.core.constants` — Timeouts, page sizes, max retries, fees
- `backend.app.core.rate_limiter` — Token-bucket (eBay: 5 burst/2 refill, Gemini: 2 RPM)
- `backend.app.core.token_manager` — Token lifecycle (refresh, storage, thread safety)
- `backend.app.core.validator` — Category, price, condition validation
- `backend.app.core.models` — InternalListing dataclass (adapter target)

**External:**
- `requests` — HTTP client for REST APIs
- `xml.etree.ElementTree`, `xml.sax.saxutils` — XML parsing/escaping (Trading API)
- `base64` — OAuth token encoding/decoding
- `sqlite3` — Persistent taxonomy cache
- `threading` — Thread-safe token refresh
- `urllib.parse` — OAuth URL parameter encoding
- `webbrowser` — OAuth redirect URI (auth.py)
- `dotenv` — Environment variables (credentials)

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
