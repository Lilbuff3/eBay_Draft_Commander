# Gemini Context — eBay Draft Commander

Context order: read `AGENTS.md` (cross-tool summary + hard rules), then `CLAUDE.md` (authoritative architecture, patterns, gotchas — kept current).

## Hard rules (rails enforced by .agents/hooks.json where applicable)
1. Never edit `.env` directly — use SettingsManager / Settings UI / `/api/settings`. (Hard blocked by hook)
2. Never hand-edit `static/app/` — change `frontend/src`, run `npm run build`, commit build + source together. (Hard blocked by hook)
3. Never commit `data/commander.db` from a feature branch.
4. Restart backend after backend changes: `POST http://127.0.0.1:5000/api/system/restart` (no hot reload; 409 = unsupervised).
5. Run `npx eslint` on changed frontend files (auto-triggered by post-tool hook).
6. Tests: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit -q` and `cd frontend && npx vitest run`.
7. Pull master before starting; push before stopping (Claude Code sessions share this repo).

Skills available in `.agents/skills/` (trigger via `/<name>`): run-backend, run-frontend, build-frontend, run-tests, restart-backend.
