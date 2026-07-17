# Working on Draft Commander with Gemini in Antigravity

Owner setup guide — how to develop this project in Google Antigravity 2 with Gemini, alongside occasional Claude Code sessions.

## 1. Open the project

Antigravity → **Open Folder** → `C:\Users\adam\Projects\ebay-draft-commander`

Always this path. Never the old OneDrive location, never anything under `.claude\worktrees\`.

## 2. Verify the agent loaded project context

Ask the agent: *"What's the unit test command for this project?"*

Correct answer cites `"C:\Program Files\Python312\python.exe" -m pytest tests/unit -q`. If it says plain `pytest`, context didn't load — check that `AGENTS.md` / `GEMINI.md` exist at the workspace root and re-open the folder.

Context files, in priority order:
- `AGENTS.md` — thin cross-tool summary + the hard rules (Antigravity reads this natively)
- `GEMINI.md` — same rules, Gemini-convention filename
- `CLAUDE.md` — the deep authoritative reference; tell the agent to read it before non-trivial work

## 3. Register the eBay MCP server (optional but recommended)

Gives Gemini the same read-only eBay tools Claude has (search, category suggest, aspects, price research, orders, token status).

Antigravity Settings → MCP servers → add:
- **command**: `C:\Program Files\Python312\python.exe`
- **args**: `backend/mcp_server.py`
- **cwd**: `C:\Users\adam\Projects\ebay-draft-commander`

(Mirrors `.mcp.json`, which Claude Code uses. All tools are read-only — no listing mutations.)

Verify: ask the agent to call `ebay_token_status`.

## 4. Use the workflows

Type these in the agent panel (they live in `.agent/workflows/`):
- `/run-backend` — dev foreground or supervised background (supervised enables one-click restart)
- `/run-frontend` — Vite dev server on 5175
- `/run-tests` — backend pytest (Python 3.12) + frontend vitest
- `/build-frontend` — production build into `static/app/` (run before committing frontend changes)
- `/restart-backend` — required after every backend change (no hot reload)

## 5. Two-agent hygiene (Gemini here + Claude Code sessions)

Both agents push to GitHub `master`. To avoid stepping on each other:
- **Start every session with `git pull`** — a Claude session may have pushed since you last looked
- **End every session with a push** — never leave unpushed commits
- One agent per branch at a time; feature branches for anything non-trivial, merge to master when green
- If a merge conflicts in `static/app/*`, don't hand-resolve — rebuild (`/build-frontend`) and stage the fresh output

## 6. Quirks Gemini will hit (all known, all benign)

- **cp1252 logging errors** with emojis in console output — cosmetic, never crashes the pipeline
- **rembg downloads ~170MB** ONNX model on first image-processing run
- **`/api/system/restart` returns 409** when the backend was started as `python backend/wsgi.py` (unsupervised) — relaunch via `/run-backend` supervised mode
- **Phone HTTPS is Tailscale**, not Caddy: `tailscale serve --bg 5000` → `https://tuf-2.taile466a6.ts.net`. If the phone URL dies, check `tailscale status` for a logged-out daemon
- **Remote API calls need `X-API-Key`** (loopback is exempt) — relevant only if testing from another device
