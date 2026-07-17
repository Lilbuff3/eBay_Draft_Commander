---
description: Start the Flask backend (dev foreground or supervised background)
---

## Start Backend

Two ways to run it — pick by need:

**Dev (foreground, logs in terminal, no one-click restart):**
```
cd C:\Users\adam\Projects\ebay-draft-commander && python backend/wsgi.py
```

**Supervised background (production-style — enables POST /api/system/restart):**
```powershell
cd C:\Users\adam\Projects\ebay-draft-commander; Start-Process pythonw backend\run_service.py
```

Notes:
- Port 5000. Serves the API and the built React app at `/app/`.
- The supervisor (`run_service.py`) relaunches the server on exit code 42 — that's what powers the one-click `/api/system/restart`. Launched via `wsgi.py` directly, `/restart` returns 409 and you must restart manually.
- Logs (supervised mode): `data/backend_service.log`.
