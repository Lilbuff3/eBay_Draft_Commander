---
description: Restart the running backend to pick up backend code changes
---

## Restart Backend

Backend has **no hot reload** — every backend change needs a restart to take effect.

// turbo
1. One-click restart (works when running under the supervisor):
```
curl -X POST http://127.0.0.1:5000/api/system/restart
```

2. Verify it came back:
```
curl http://127.0.0.1:5000/api/system/health
```

If the restart call returns **409**, the backend was launched without the supervisor (`python backend/wsgi.py`) — stop it and relaunch via /run-backend supervised mode.
