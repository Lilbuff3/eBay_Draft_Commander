<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# core

## Purpose
Foundation layer with zero internal dependencies. Provides database models, constants, validation, logging, settings, token management, rate limiting, and results logging. Core is depended on by blueprints and services but depends on nothing else.

## Key Files

| File | Description |
|------|-------------|
| `constants.py` | CONDITION_MAP, CONDITION_ID_MAP, rate limits, default aspects, image extensions, fees, timeouts |
| `database.py` | SQLAlchemy 2.0 ORM — JobModel, TemplateModel, OrphanedMediaModel, AppTokenModel with WAL pragmas |
| `models.py` | InternalListing dataclass — adapter for normalizing eBay API responses |
| `exceptions.py` | DraftCommanderError base, eBayAPIError subtypes, NeedsReviewException for manual review routes |
| `logger.py` | `get_logger(name)` factory — JSON/console handlers, Windows cp1252 emoji safety |
| `paths.py` | `get_data_dir()`, `get_inbox_dir()`, `get_cache_dir()` — cross-platform path handling |
| `settings_manager.py` | Singleton `.env` reader/writer with caching and auto-refresh on file changes |
| `token_manager.py` | eBay OAuth token persistence, background refresh thread, 401 auto-refresh |
| `rate_limiter.py` | Token-bucket rate limiting — Gemini 2 RPM, eBay 5 burst/2 sec refill |
| `validator.py` | Input validation: `validate_price()`, `validate_title()`, `validate_isbn()`, `validate_condition()` |
| `results_logger.py` | JSONL logger to `data/listing_results.jsonl` with `log_listing_result()` and `get_results()` |
| `prompts.py` | AI prompt templates for Gemini vision, pricing, and specifics analysis |

## For AI Agents

### Working In This Directory
- Core has **zero internal dependencies** — only stdlib, SQLAlchemy, dotenv
- SettingsManager and TokenManager are singletons — `SettingsManager()`, `TokenManager()`
- Use `get_logger(__name__)` for module logging; avoid emoji on Windows (cp1252 encoding)
- Use path helpers — never hardcode paths
- Add custom exceptions inheriting from `DraftCommanderError`
- Check rate limiter before eBay/Gemini calls: `RateLimiter.try_acquire('gemini')`

### Key Patterns
- **Logger setup**: `logger = get_logger(__name__)` at module top
- **Path handling**: `from core.paths import get_data_dir; data_dir = get_data_dir()`
- **Settings**: `sm = SettingsManager(); api_key = sm.get('EBAY_CLIENT_ID')`
- **Token refresh**: `tm = TokenManager(); if tm.is_expired(): tm.refresh_if_needed()`
- **Rate limiting**: `rl = RateLimiter(); if not rl.try_acquire('gemini'): raise Exception("rate limited")`
- **Validation**: `from core.validator import validate_price; validate_price(price)` raises ValueError on failure

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
