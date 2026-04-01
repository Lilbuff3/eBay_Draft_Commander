<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# store

## Purpose
Single Zustand store (`useCommanderStore`) managing all app state: jobs, queue status, logs, navigation, upload progress, and async actions.

## Key Files

| File | Description |
|------|-------------|
| `useCommanderStore.ts` | `CommanderState` interface + implementation. State (jobs, queueStats, logs, activeTab, filters) + actions (handleStart, handlePause, handleScan, setJobs, addLog, etc.) |

## For AI Agents

### Working In This Directory
- Access state via selectors: `useCommanderStore(state => state.jobs)` — auto-memoized
- Mutations only via actions — never call `setState` directly in components
- `activeTab` persisted to localStorage via `setActiveTab` action
- `useJobSync()` hook syncs Socket.IO events → store via `setJobs`, `setQueueStats`, `addLog`
- `addLog` keeps last 100 entries per job (`.slice(-100)`)
- Async actions use try/catch + `toast` for error handling

### Key State Groups
- **Navigation**: `activeTab`, `previousTab`, `setActiveTab()`
- **Jobs**: `jobs`, `selectedJob`, `pendingListings` + setters
- **Queue**: `queueStats`, `isProcessing`, `ebayStatus` + setters
- **Logs**: `jobLogs` (Record<string, LogEntry[]>), `addLog()`
- **Actions**: `handleStart()`, `handlePause()`, `handleScan()`, `fetchPending()`, `updatePending()`, `approvePending()`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
