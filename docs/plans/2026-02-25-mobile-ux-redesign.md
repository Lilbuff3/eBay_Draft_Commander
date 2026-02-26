# Mobile UX Redesign — Sticky + Compact Layout

**Date:** 2026-02-25
**Branch:** feature/mobile-ux-redesign
**Scope:** Mobile-only changes (< md breakpoint). Desktop unchanged.

## Problem

The Dashboard renders 300+ items in a 2-column thumbnail grid with ~350px of non-content header above the fold. Users see ~2 items per screen and lose filter/action controls on scroll. This makes the "full workflow on mobile" use case painful.

## Design

### 1. Sticky Header (84px total, mobile only)

**Row 1 — Title bar (44px):**
- Left: "Workspace" (text-lg font-bold) + muted count badge "317"
- Right: Status dot indicator (green pulse = processing, red = eBay offline, gray = idle) + overflow menu button (vertical dots)
- Overflow menu contains: Scan Inbox, Process All, Clear Failed, Clear Done

**Row 2 — Filter chips (40px, horizontal scroll):**
- Pill-shaped chips: All 317 | Inbox 1 | Processing | Action 295 | History 21
- Active = filled sage background, inactive = ghost/outlined
- Horizontal scroll, no wrapping
- "Action Needed" shortened to "Action" on mobile

Both rows position: sticky, top: 0, z-index: 40. Subtle border-bottom when scrolled.

### 2. Compact Item List (mobile only)

Switch from 2-column grid to single-column compact rows. Each row ~68px:

```
+--------------------------------------+
| [48px   ]  Title text here   [Failed]|
| [thumb  ]  Condition · Error      >  |
+--------------------------------------+
```

- 48x48 square thumbnail with rounded corners, fallback icon if no image
- Title: 1 line, truncated with ellipsis
- Status badge: colored pill, right-aligned (Failed=red, Completed=green, Processing=amber, Pending=gray)
- Subtitle: condition label + error type, text-xs text-stone-400
- Tap opens detail drawer
- Long-press enters bulk selection mode (checkbox appears on left)
- Desktop (md+) keeps existing 2+ column card grid unchanged

Expected: ~10 items visible per screen (vs ~2 today)

### 3. Upload FAB (mobile only)

- Remove UploadZone section from mobile layout entirely
- Add floating action button: 56px circle, bottom-right corner, positioned above MobileNavBar
- Sage/green color, "+" icon, subtle shadow
- Tap triggers the same file input (camera + gallery)
- Desktop keeps the existing drop zone

### 4. Detail Drawer Improvements

- Keep 85vh bottom sheet on mobile
- Add sticky "Create eBay Listing" button at bottom of drawer (not inside scroll area)
- Image carousel full-bleed at top with horizontal swipe

### 5. Out of Scope

- Bottom nav bar (already good)
- Desktop layout (all changes are md: conditional)
- Virtualization (defer to later — compact rows reduce DOM pressure)
- Swipe gestures (defer to later)
- Settings, Analytics, other tabs

## Files to Modify

1. `frontend/src/pages/Dashboard.tsx` — Conditional mobile layout, remove UploadZone on mobile
2. `frontend/src/components/ItemCardGrid.tsx` — Add compact list variant, sticky header, filter chip redesign
3. `frontend/src/components/MobileUploadFAB.tsx` — NEW: Floating action button component
4. `frontend/src/components/ItemDetailDrawer.tsx` — Sticky CTA button, image carousel
5. `frontend/src/components/CompactItemRow.tsx` — NEW: Single-row item component for mobile
6. `frontend/src/components/MobileStickyHeader.tsx` — NEW: Sticky header with overflow menu
7. `frontend/src/App.tsx` — Add MobileUploadFAB alongside MobileNavBar

## Implementation Order

1. MobileStickyHeader (sticky title + filter chips)
2. CompactItemRow (single-row item component)
3. ItemCardGrid refactor (swap grid for list on mobile)
4. MobileUploadFAB (floating add button)
5. Dashboard.tsx integration (wire it together)
6. ItemDetailDrawer improvements (sticky CTA)
7. Visual polish and testing
