---
name: run-backend
description: Start the Flask backend server in dev foreground mode or supervised background mode. Use when starting development or testing the backend.
---

# Start Backend Service

Two ways to run it — pick by need:

## 1. Dev Mode (Foreground)
Logs stream in terminal, but does not support one-click `/restart`:
```powershell
cd C:\Users\adam\Projects\ebay-draft-commander
python backend/wsgi.py
```

## 2. Supervised Background Mode
Production-style execution — enables `POST /api/system/restart`:
```powershell
cd C:\Users\adam\Projects\ebay-draft-commander
Start-Process pythonw backend\run_service.py
```

### Key Notes
- **Port:** 5000. Serves the API and the built React app at `/app/`.
- **Supervisor mechanism:** The supervisor (`run_service.py`) relaunches the server on exit code 42 — that's what powers the one-click `/api/system/restart`. If launched via `wsgi.py` directly, `/restart` returns 409 and you must restart manually.
- **Logs:** In supervised mode, logs are written to `data/backend_service.log`.
