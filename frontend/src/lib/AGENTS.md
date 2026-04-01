<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# lib

## Purpose
Utility layer: typed HTTP client, helpers, input sanitization, PWA lifecycle, offline queue. Pure TypeScript — no UI components.

## Key Files

| File | Description |
|------|-------------|
| `api.ts` | Typed HTTP client (`apiFetch<T>`), all API type definitions (Job, JobStatus, QueueStats, JobDetails, ItemDraft, etc.), and REST endpoint functions |
| `utils.ts` | `cn()` for merging Tailwind class names (clsx + tailwind-merge) |
| `sanitizer.ts` | `sanitizeDescription()` — removes XSS vectors, preserves safe HTML formatting |
| `pwa.ts` | PWA lifecycle — install prompt, update detection, cache invalidation |
| `offlineQueue.ts` | Stores failed requests in localStorage, replays when online |

## For AI Agents

### Working In This Directory
- `api.ts` is the source of truth for all TypeScript types — update here when backend API contract changes
- `apiFetch()` throws on `!res.ok` — callers must try/catch
- API base path is `/api` (relative) — Flask serves SPA and API on same origin
- These files are imported everywhere — if any is missing, nothing compiles
- No caching in api.ts — React Query handles that via hooks

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
