<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# hooks

## Purpose
Custom React hooks for Socket.IO synchronization, mobile detection, haptic feedback, and pull-to-refresh gestures.

## Key Files

| File | Description |
|------|-------------|
| `useJobSync.ts` | Socket.IO + React Query integration — syncs `job_added`, `job_update`, `job_log` to Zustand store. Falls back to 5s HTTP polling if Socket.IO disconnects. |
| `useIsMobile.ts` | Viewport width < 768px detection (Tailwind `md` breakpoint). Updates on resize. |
| `useHaptics.ts` | Mobile vibration wrapper — `success()` (50ms) and `error()` (double pulse). Silent fallback on desktop. |
| `usePullToRefresh.ts` | Pull-down gesture detection (currently disabled). |

## For AI Agents

### Working In This Directory
- Reuse single Socket.IO instance via `socketRef.current` — don't create multiple connections
- Hooks call Zustand store actions to sync data — components react to store changes via selectors
- Error toasts belong in calling components, not in hooks
- Be explicit in `useEffect` dependency arrays
- Always return cleanup functions from `useEffect` (socket disconnect, listener removal)

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
