<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# blueprints

## Purpose
Flask blueprints for HTTP routing and SPA serving. Thin request handlers that validate input and delegate business logic to services.

## Key Files

| File | Description |
|------|-------------|
| `api/__init__.py` | Blueprint registration hub — imports and registers 8 API sub-blueprints with `/api/` prefix, global error handlers |
| `api/jobs_api.py` | Job CRUD: create, read, update, delete, image upload, thumbnail generation, image reorder |
| `api/queue_api.py` | Queue control: `/api/start`, `/api/pause`, `/api/skip`, `/api/retry`, `/api/status` (no `/queue/` prefix) |
| `api/listings_api.py` | Active eBay listing management: status, fetch, update, end, legacy import |
| `api/lookup_api.py` | Reference data: ISBN metadata, category suggestions, aspect schema, condition validation |
| `api/analytics_api.py` | Seller analytics: active count, revenue, category breakdown |
| `api/settings_api.py` | Settings CRUD: read/write `.env` via SettingsManager (masked sensitive values) |
| `api/system_api.py` | System operations: health check, restart, cache clear (prefix: `/api/system/`) |
| `api/migration_api.py` | Data migration helpers: legacy listing import, validation |
| `api/helpers.py` | Shared utilities: `error_response(message, code, details)` for consistent JSON errors |
| `ui.py` | React SPA serving: `/app/`, manifest, service worker, static assets, favicon |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `api/` | REST API sub-modules by domain (see `api/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Routes validate input with `core.validator` before passing to services
- Routes delegate business logic to services — never contain complex logic
- Use `error_response(message, code)` from helpers for consistent JSON error format
- Socket.IO events emitted by services, not routes
- File uploads use `secure_filename()` and validate MIME types
- See CLAUDE.md for complete route list, prefixes, and request/response schemas

### Key Patterns
- **Error handling**: All unhandled exceptions caught by global handler in `api/__init__.py`
- **Validation**: Use `core.validator` before service calls, return 400 if invalid
- **Success responses**: Vary by endpoint but typically `{success: true, data: {...}}` or direct data
- **File uploads**: Check MIME type, validate dimensions, secure filename
- **Database**: SQLAlchemy models accessed via services, not routes
- **Rate limiting**: Enforced by services before API calls, not in routes

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
