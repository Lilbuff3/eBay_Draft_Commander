<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# backend/app/blueprints/api

## Purpose
REST API sub-modules organized by functional domain. Each module defines a Blueprint with routes prefixed `/api/` plus domain-specific paths. Modules are registered in `__init__.py` with shared error handlers and request validation.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Blueprint registration hub — imports 8 sub-blueprints, registers with `/api/` prefix, global 400/404/500 error handlers |
| `helpers.py` | `error_response(message, code, details)` for standardized JSON error format |
| `jobs_api.py` | Job CRUD: POST/GET/PUT/DELETE, image upload, thumbnail generation, image reorder, inbox detection, OneDrive fallback |
| `queue_api.py` | Queue control: `/start`, `/pause`, `/skip`, `/retry`, `/status` — real-time job progress via QueueManager |
| `listings_api.py` | eBay listings: status check, fetch active, update, end, legacy import via Trading API |
| `lookup_api.py` | Reference lookups: ISBN metadata, category suggestions with aspects, condition validation |
| `analytics_api.py` | Seller metrics: active listings, revenue, category breakdown via Analytics API |
| `settings_api.py` | Settings: read masked `.env`, write single setting via SettingsManager |
| `system_api.py` | System operations: health check, restart, cache clear (taxonomy, rate limiter) |
| `migration_api.py` | Legacy data: import listings, validate migration source |

## For AI Agents

### Working In This Directory
- **Add endpoint**: Create sub-module (e.g., `reports_api.py`), define Blueprint with routes, import and register in `__init__.py`
- **Modify endpoint**: Find route in sub-module, update handler — validate input, call service, return error_response on failure
- **Error format**: Use `error_response(message, code)` → `{success: false, error: "...", details: {...}}`
- **Validation**: Import from `core.validator`, return 400 if invalid
- **File uploads**: Use `secure_filename()`, validate MIME type, check dimensions
- **Context access**: Use `current_app.config['KEY']` for config, `current_app.queue_manager` for QueueManager

### Common Patterns
- **Input validation**: Check request.json, validate with `core.validator`, return 400 on error
- **Database access**: Call services (not models directly) — services handle DB operations
- **Rate limiting**: Checked by services before eBay/Gemini calls
- **Socket.IO events**: Services emit `job_added`, `job_update`, `job_log` for UI sync
- **Async operations**: QueueManager processes jobs in background thread
- **Success response**: Vary by endpoint — typically `{success: true, data: {...}}` or `{success: true}`

### Dependencies

**Internal:**
- `backend.app.core.logger` — Module-level logging
- `backend.app.core.validator` — Input validation (price, title, ISBN, condition)
- `backend.app.core.constants` — Shared constants (image extensions, rate limits, timeouts)
- `backend.app.core.settings_manager` — `.env` read/write
- `backend.app.core.token_manager` — eBay token lifecycle
- `backend.app.services.queue_job` — JobStatus enum, thumbnail resolution
- `backend.app.services.image_service` — Image upload/processing
- `backend.app.services.ebay_service` — eBay API facade
- `backend.app.services.ebay.policies` — Business policies lookup
- `backend.app.services.ebay.taxonomy` — Category/aspect schema
- `backend.app.services.book_service` — ISBN metadata lookup

**External:**
- `flask` — Blueprint, request, jsonify, current_app, send_file
- `werkzeug` — secure_filename
- `pathlib` — Cross-platform path handling

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
