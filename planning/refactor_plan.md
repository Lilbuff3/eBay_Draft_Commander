# Backend Refactor Plan: Service-Oriented Architecture

## Goal
Decompose the monolithic `web_server.py` (1700+ lines) into a modular, maintainable Flask application structure. This aligns with the "Governance" directive to eliminate "Giant Scripts".

## Proposed Structure
We will create a new package `backend/` to house the application logic.

```text
backend/
├── app/
│   ├── __init__.py          # App Factory (create_app)
│   ├── blueprints/
│   │   ├── api.py           # API Routes (/api/...)
│   │   └── ui.py            # UI Routes (serving React/Templates)
│   ├── services/
│   │   ├── ebay_service.py  # eBay API logic
│   │   ├── queue_service.py # Queue management
│   │   └── image_service.py # Photo editing logic
│   └── models/
│       └── job.py           # Data structures
├── config.py                # Flask Configuration
└── wsgi.py                  # Entry point (replaces web_server.py)
```

## Step-by-Step Implementation

1.  **Scaffold Directory**: Create folders `backend/app`, `backend/app/blueprints`, `backend/app/services`.
2.  **Move Logic**:
    *   Extract `eBayOrders`, `Trading API` calls -> `services/ebay_service.py`.
    *   Extract `QueueManager` integration -> `services/queue_service.py`.
3.  **Create Blueprints**:
    *   Move `@app.route('/api/...')` -> `blueprints/api.py`.
    *   Move `@app.route('/')` and static serving -> `blueprints/ui.py`.
4.  **Application Factory**:
    *   Implement `create_app()` in `app/__init__.py`.
5.  **Entry Point**:
    *   Create `wsgi.py` that imports `create_app` and runs it.
    *   Update `frontend/electron/main.cjs` to spawn `wsgi.py` (or keep `web_server.py` as a shim).

## Verification Plan
1.  **Unit Test**: Run `test_trading_api.py` to ensure services still work.
2.  **Integration Test**: Launch Electron app (`npm run electron:dev`) and verify Dashboard loads.
3.  **Feature Test**: "Scan Inbox" and "Save Settings" must function identical to before.

## User Review Required
*   **Breaking Change**: The entry point filename will change. This affects `server.spec` (PyInstaller) and `main.cjs` (Electron). I will update these, but verified breakage is possible during the transition.
