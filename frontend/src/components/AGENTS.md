<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# components

## Purpose
React components: dashboard views, modals, forms, image gallery, mobile capture, barcode scanning, and shadcn/Radix primitives.

## Key Files

| File | Description |
|------|-------------|
| `ItemDetailDrawer.tsx` | Modal drawer for viewing/editing job details — title, condition, price, category, images, specifics, scheduling, profit calculator |
| `ImageGallery.tsx` | @dnd-kit drag-and-drop image reordering (first image = eBay cover photo) with upload zone |
| `LogViewer.tsx` | Expandable job processing log viewer with timestamps |
| `ActiveListings.tsx` | Live eBay listings tab with selection, bulk actions, filtering |
| `MobileUploadFAB.tsx` | Floating action button for phone/mobile uploads with ripple animation |
| `MobileNavBar.tsx` | Bottom navigation for mobile views (Dashboard, Settings, Scanner) |
| `ErrorBoundary.tsx` | React error boundary with fallback UI and error logging |
| `InstallPrompt.tsx` | PWA install banner with deferral and install tracking |
| `ScannerListener.tsx` | Background scanner event listener |
| `BatchSummaryDialog.tsx` | Batch operation summary and progress dialog |
| `ShippingSelector.tsx` | Shipping method and cost selector |
| `OfflineIndicator.tsx` | Visual indicator for offline status and sync state |
| `MigrationModal.tsx` | Data migration and legacy settings migration dialog |
| `Sidebar.tsx` | Navigation sidebar for desktop layout |
| `MobileCaptureSheet.tsx` | Two-phase capture ⇄ success sheet; owns ALL upload feedback (no toasts elsewhere) |
| `CameraBarcodeScanner.tsx` | Native BarcodeDetector with lazy ZXing fallback; optional `formats`/`validate` props |
| `CategoryPicker.tsx` | eBay category chooser; selection sticks in localStorage `dc-capture-category` |
| `UploadZone.tsx` | Drag-and-drop / file-picker upload entry point |
| `ApiKeyDialog.tsx` | Prompts once for `X-API-Key` on a 401 from a non-loopback client |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `ui/` | shadcn/Radix primitives (see `ui/AGENTS.md`) |
| `item-detail/` | Item description/schedule cards (see `item-detail/AGENTS.md`) |
| `listings/` | Inventory cockpit card + review queue (see `listings/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Components use Zustand store (`useCommanderStore`) — check store actions before adding new props
- All API calls through `src/lib/api.ts` (`apiFetch<T>`)
- Use `toast()` from sonner for notifications (no `alert()`)
- Mobile layout: check `useIsMobile()` hook; Tailwind breakpoints for responsive
- Type definitions in `src/lib/api.ts` (Job, JobDetails, ItemDraft, etc.)
- Condition field: frontend sends as `{label, value}` object; backend extracts `.value`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
