<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# app

## Purpose
Flask application package. Implements app factory pattern with `create_app()`, blueprint registration, Socket.IO initialization, and three-layer architecture (blueprints, core, services).

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | `create_app(queue_manager)` — Flask initialization, Socket.IO setup, blueprint registration, QueueManager injection |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `blueprints/` | HTTP routing layer — REST API endpoints, SPA serving, error handlers (see `blueprints/AGENTS.md`) |
| `core/` | Foundation layer — models, constants, validation, logging, settings, token mgmt (see `core/AGENTS.md`) |
| `services/` | Business logic layer — AI, pricing, images, queue, eBay integration (see `services/AGENTS.md`) |
| `static/` | Compiled React SPA and static assets |

## For AI Agents

### Working In This Directory
- QueueManager injected via `create_app(queue_manager=qm)` and accessible as `app.queue_manager`
- Socket.IO singleton created in `__init__.py` — QueueManager uses it for `job_added`, `job_update`, `job_log` events
- All three layers depend only on `core` — no circular imports
- See CLAUDE.md for full pipeline, pricing cascade, condition chain, and API route list

### Key Patterns
- Services register global error handlers (400, 404, 500)
- Blueprints registered with URL prefixes (e.g., `/api/`, `/app/`)
- Socket.IO namespaces emit to all connected clients for real-time UI sync

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
