<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# src

## Purpose
React application source. Tab-based navigation (no react-router), Zustand single-store state, Socket.IO real-time sync, PWA-enabled mobile-first UI.

## Key Files

| File | Description |
|------|-------------|
| `App.tsx` | Root component — tab routing, Framer Motion page transitions, mobile/desktop layouts, Socket.IO init |
| `main.tsx` | React root — QueryClient setup (30s staleTime), strict mode |
| `index.css` | Tailwind directives + global styles |
| `mobile.css` | Mobile-specific overrides (viewport, touch gestures) |
| `sw.ts` | Service worker — precache, network-first runtime, offline fallback |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `components/` | 30+ UI components (see `components/AGENTS.md`) |
| `pages/` | Dashboard, Settings, BatchScan (see `pages/AGENTS.md`) |
| `store/` | Zustand store — single source of truth (see `store/AGENTS.md`) |
| `hooks/` | Custom hooks — Socket.IO sync, mobile detection (see `hooks/AGENTS.md`) |
| `lib/` | API client, utils, sanitizer, PWA, offline queue (see `lib/AGENTS.md`) |
| `test/` | Vitest setup and test utilities |

## For AI Agents

### Working In This Directory
- Tab navigation via `activeTab` in Zustand store — no react-router
- All API calls through `apiFetch<T>()` in `lib/api.ts`
- Types (Job, QueueStats, etc.) defined in `lib/api.ts`
- Use `useIsMobile()` for responsive conditional rendering (breakpoint: 768px)
- Use `toast()` from sonner for notifications
- Use shadcn/Radix primitives from `components/ui/` — don't build custom inputs

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
