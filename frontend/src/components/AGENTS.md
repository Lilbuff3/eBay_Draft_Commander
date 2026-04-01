<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# components

## Purpose
28+ React components: dashboard views, modals, forms, image gallery, mobile UI, and shadcn/Radix primitives. Handles job listing, editing, analytics, media management, and PWA install prompts.

## Key Files

| File | Description |
|------|-------------|
| `ItemDetailDrawer.tsx` | Modal drawer for viewing/editing job details — title, condition, price, category, images, specifics, scheduling, profit calculator |
| `ItemCardGrid.tsx` | Responsive grid layout for job cards with filtering and sorting |
| `ItemCard.tsx` | Individual job card component — title, status badge, thumbnail, progress bar |
| `CompactItemRow.tsx` | Compact list view for jobs (alternative to grid layout) |
| `ImageGallery.tsx` | @dnd-kit drag-and-drop image reordering (first image = eBay cover photo) with upload zone |
| `LogViewer.tsx` | Expandable job processing log viewer with timestamps |
| `ActiveListings.tsx` | Live eBay listings tab with selection, bulk actions, filtering |
| `AnalyticsDashboard.tsx` | Queue stats, completion rate, revenue charts, daily metrics |
| `MobileUploadFAB.tsx` | Floating action button for phone/mobile uploads with ripple animation |
| `MobileNavBar.tsx` | Bottom navigation for mobile views (Dashboard, Settings, Scanner) |
| `ErrorBoundary.tsx` | React error boundary with fallback UI and error logging |
| `ConfirmDialog.tsx` | Reusable confirmation modal for destructive actions |
| `InstallPrompt.tsx` | PWA install banner with deferral and install tracking |
| `PhotoEditor.tsx` | Image cropping, rotation, brightness/contrast adjustment |
| `TemplateManager.tsx` | Listing template management — save, load, edit templates |
| `PreviewPanel.tsx` | Live eBay listing preview with HTML rendering |
| `PriceResearch.tsx` | Market research panel for price suggestions |
| `QuickListingForm.tsx` | Quick listing form for rapid item entry |
| `ScannerModal.tsx` | Barcode scanner modal with ISBN detection |
| `ScannerListener.tsx` | Background scanner event listener |
| `BatchSummaryDialog.tsx` | Batch operation summary and progress dialog |
| `ShippingSelector.tsx` | Shipping method and cost selector |
| `OfflineIndicator.tsx` | Visual indicator for offline status and sync state |
| `PullToRefreshIndicator.tsx` | Pull-to-refresh animation indicator |
| `MigrationModal.tsx` | Data migration and legacy settings migration dialog |
| `Sidebar.tsx` | Navigation sidebar for desktop layout |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `ui/` | shadcn/Radix primitives (see `ui/AGENTS.md`) |
| `item-detail/` | Item description/schedule cards (see `item-detail/AGENTS.md`) |
| `listings/` | Bulk actions, edit dialog, media manager (see `listings/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Components use Zustand store (`useCommanderStore`) — check store actions before adding new props
- All API calls through `src/lib/api.ts` (`apiFetch<T>`)
- Use `toast()` from sonner for notifications (no `alert()`)
- Mobile layout: check `useIsMobile()` hook; Tailwind breakpoints for responsive
- Type definitions in `src/lib/api.ts` (Job, JobDetails, ItemDraft, etc.)
- Condition field: frontend sends as `{label, value}` object; backend extracts `.value`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
