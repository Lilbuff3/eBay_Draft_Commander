<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# backend

## Purpose
Flask REST API backend for eBay listing automation. Handles AI-powered listing generation, eBay API integration, queue management, real-time Socket.IO events, and system configuration.

## Key Files

| File | Description |
|------|-------------|
| `wsgi.py` | WSGI entry point — initializes QueueManager, creates Flask app, starts server on port 5000 |
| `config.py` | Configuration loader — `.env` discovery (supports git worktrees), Flask config, credential validation |
| `app/__init__.py` | App factory — `create_app(queue_manager)`, blueprint registration, Socket.IO singleton init |
| `mcp_server.py` | MCP server wrapper for external Claude integration and tool exposure |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `app/` | Flask application package — factory, blueprints, core, services (see `app/AGENTS.md`) |
| `app/blueprints/` | Flask blueprints — REST API routes, SPA serving, error handlers (see `app/blueprints/AGENTS.md`) |
| `app/core/` | Domain layer — DB models, constants, validation, logging, settings, token mgmt (see `app/core/AGENTS.md`) |
| `app/services/` | Business logic — AI, pricing, images, queue, eBay integration (see `app/services/AGENTS.md`) |
| `static/` | Static assets and compiled SPA files |

## For AI Agents

### Working In This Directory
- Start server: `python backend/wsgi.py` (port 5000, auto-reload on file changes)
- `.env` must exist in project root — `config.py` walks parent dirs to find it
- See CLAUDE.md for env vars, pipeline flow, condition hierarchy, and testing commands

### Architecture
Three-layer separation: **blueprints** (thin HTTP routing) → **services** (business logic) → **core** (models, validation, constants). API routes validate input, delegate to services, and never contain business logic.

### Key Patterns
- All request validation happens in blueprints using `core.validator`
- Services emit Socket.IO events for UI updates (never directly in routes)
- QueueManager is a singleton injected at app creation
- Rate limiting enforced by services before eBay/Gemini API calls

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
