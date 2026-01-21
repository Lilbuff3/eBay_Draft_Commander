# Architecture Migration Plan: The "Kill Tkinter" Strategy

## Goal Description
Deprecate the legacy Tkinter desktop application (`draft_commander.py`) and establish the React Web App (`frontend`) as the sole user interface, wrapped in an Electron shell. This unifies the codebase, providing a modern, consistent experience with desktop-class capabilities (drag-and-drop, isolated environment).

## User Review Required
> [!IMPORTANT]
> **Settings Migration**: The React app currently lacks a Settings interface. This must be implemented before killing Tkinter, as users will lose access to API key configuration.
> **Processor Logic**: `web_server.py` currently uses a different processing function (`analyzer.analyze_folder`) than `draft_commander.py` (`create_listing_structured`). This must be unified to ensure consistent listing creation.

## Proposed Strategy: "Headless Backend + Electron Shell"

### Phase 1: Feature Parity (React & Flask)
Before migrating, the web app must support all critical desktop features.
1.  **Implement Settings Interface in React**:
    *   Create `/settings` route and `SettingsPage.tsx`.
    *   Add API endpoints to `web_server.py` to read/write `.env` or `settings.json`.
    *   Replicate all configuration options from Tkinter.
2.  **Unify Queue Processor**:
    *   Update `web_server.py` to use `create_listing_structured` (from `create_from_folder.py`) instead of raw `analyzer.analyze_folder` to ensure identical behavior to the current desktop app.

### Phase 2: The Electron Shell
Create the desktop wrapper that manages the Python backend.
*   **Tech Stack**: Electron, `electron-builder`.
*   **Architecture**:
    *   **Main Process**: NodeJS. Spawns the Python Flask server as a child process.
    *   **Renderer Process**: The existing Vite React app.
*   **Drag & Drop**: Implement native drag-and-drop handling. Electron's `File` object exposes the full `path` property, allowing the React app to send absolute paths to the Python backend (bypassing browser sandbox limitations).

### Phase 3: Packaging & Cleanup
*   **Python Bundling**: Use PyInstaller to compile `web_server.py` and its dependencies (including `ffmpeg` if needed) into a standalone executable.
*   **Electron Bundling**: Configure `electron-builder` to include the Python executable as an extra resource.
*   **Deprecation**: Remove `draft_commander.py` and Tkinter dependencies.

## Detailed Implementation Steps

### 1. Backend Preparation
- [ ] **Unify Processor**: Modify `web_server.py` `if __name__ == "__main__":` block to import and use `create_listing_structured`.
- [ ] **Settings API**: Add `GET /api/settings` and `POST /api/settings` to `web_server.py` for managing keys (eBay, Google, etc.).

### 2. Frontend Updates
- [ ] **Settings Page**: Build `src/pages/Settings.tsx` with form fields for all env vars.
- [ ] **Drop Zone Update**: Update `Dashboard.tsx` drop handler.
    -   Host environment check: `if (window.electron) ...`
    -   If Electron: Read `file.path` directly and call `/api/queue/add` with the path.
    -   If Web: Continue current behavior (or prompt for path if possible/needed).

### 3. Electron Integration
- [ ] **Install**: `npm install electron electron-builder concurrently wait-on --save-dev` in `frontend`.
- [ ] **Main Process**: Create `frontend/electron/main.js`.
    -   Script to spawn `python` (dev) or the executable (prod).
    -   Window management.
    -   Menu bar integration (View, History, Settings).
- [ ] **Preload Script**: Create `frontend/electron/preload.js` to expose necessary APIs (if strict context isolation is used, though for internal apps `nodeIntegration: true` is practically easier if security model allows, otherwise use `contextBridge`).

### 4. Build & Distribution
- [ ] **PyInstaller Spec**: Create `server.spec` to bundle `web_server.py`.
- [ ] **Electron Builder**: Configure `package.json` build scripts.

## Verification Plan
1.  **Feature Check**: Verify Settings, Queue, and Inventory Sync work identical to Tkinter.
2.  **Drag & Drop**: Verify dragging a folder from Windows Explorer correctly queues it in the Electron app.
3.  **Distribution**: Verify the final `.exe` installs and runs without requiring Python to be installed on the host.
