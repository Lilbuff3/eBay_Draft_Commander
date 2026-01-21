---
name: Project Workflow & Management
description: Detailed instructions for building, running, and managing the eBay Draft Commander Electron application.
---

# Project Workflow Expert Guide

This skill guides the AI in managing the eBay Draft Commander project, specifically handling the complex interaction between the React Frontend, Electron Shell, and Python Backend.

## 1. Project Architecture (Mental Model)
- **Frontend**: React + Vite + Tailwind (located in `/frontend`).
- **Backend**: Python Flask (`web_server.py` in root).
- **Electron**: Wraps both. In `dev` mode, it launches the Python backend as a subprocess.
- **Data**: Uses `.env` for configuration and local JSON/SQLite for storage.

## 2. Critical Commands

Always run these commands from the `frontend/` directory unless specified otherwise.

### Development
- **Start Full App**: `npm run electron:dev`
    - *Why*: Starts Vite server AND Python backend AND Electron window.
    - *Do NOT*: Do not run `npm run dev` alone unless you only want the web UI without desktop features.
    - *Note*: Ensure no orphan `python.exe` processes are running if port 5000 is blocked.

### Build & Distribution
- **Build Production**: `npm run electron:build`
    - *Prerequisite*: Run `pyinstaller server.spec` in the project root FIRST to bundle the Python backend.
    - *Output*: Installer uses `nsis` config in `package.json`.

### Testing
- **Backend Tests**: Run `python -m scripts.test_trading_api` or `python -m scripts.test_ebay_offers` from the project root.

## 3. Best Practices for Changes

### Modifying Backend Logic
1.  Edit `web_server.py`.
2.  **Restart Required**: The Electron app does *not* hot-reload Python changes. You must kill the terminal and run `npm run electron:dev` again.

### Modifying Frontend logic
1.  Edit `*.tsx` files.
2.  **No Restart Needed**: Vite Hot Module Replacement (HMR) handles this instantly.

### Adding Dependencies
- **Frontend**: `npm install <package>` in `/frontend`.
- **Backend**: `pip install <package>` root, and **UPDATE** `requirements.txt` immediately.

## 4. Common Issues & Fixes
- **"Port 5000 in use"**: The Python backend didn't close properly.
    - *Fix*: `taskkill /F /IM python.exe` (Windows) or `pkill -f python` (Linux/Mac).
- **"Electron failed to fetch"**: Python backend crashed on startup.
    - *Check*: Look at the terminal output for Python tracebacks.
