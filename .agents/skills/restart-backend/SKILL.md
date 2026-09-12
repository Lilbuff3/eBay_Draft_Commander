---
name: restart-backend
description: Restart the running Flask backend daemon to pick up backend Python changes. Use after modifying backend code.
---

# Restart Backend Service

The Flask backend has **no hot reload** — every backend change requires a restart to take effect.

## Steps
1. One-click restart (works when running under the supervisor):
   ```powershell
   curl.exe -X POST http://127.0.0.1:5000/api/system/restart
   ```

2. Verify it came back:
   ```powershell
   curl.exe http://127.0.0.1:5000/api/system/health
   ```

3. If the restart call returns **409**, the backend was launched without the supervisor (`python backend/wsgi.py`) — stop it in its terminal and relaunch via `/run-backend` supervised mode.
