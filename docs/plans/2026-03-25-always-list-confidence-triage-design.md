# Always List, Confidence Triage — UX Overhaul Design

**Date:** 2026-03-25
**Status:** Approved

## Problem

The current dashboard conflates "needs review" (missing item specifics) with "failed" (actual errors) under an "Action Needed" tab. Items that processed successfully but lack a few specifics appear as failures, creating the perception that the system is broken. Users don't return to review blocked items, so they pile up.

The `pending_review` / `needs_review` gate stops items from being listed until manually approved — but the whole point of the tool is to minimize manual work.

## Core Philosophy Change

**Current:** Process → hit a guard → block as `pending_review` → wait for user → items pile up.

**New:** Process → AI fills everything (best guess) → always schedule on eBay → show confidence scores → user triages on their own time via eBay's editor.

Nothing blocks. Nothing says "failed" unless it actually failed. The dashboard is a processing monitor and confidence triage board, not a review queue.

## Design

### 1. Backend — "Never Block" Pipeline

- **Remove the `pending_review` gate.** The processor no longer routes to review for missing aspects, low confidence, or low price.
- **AI fills all required aspects.** Expand beyond `SAFE_DEFAULT_ASPECTS` — use Gemini to make best guesses for category-specific fields (Size, Color, etc.) instead of "Does Not Apply" where possible.
- **Per-field confidence tracking.** Each item specific gets a confidence level:
  - `high` — from product data, ISBN, or strong image match
  - `medium` — AI-inferred from images/research
  - `low` — pure guess or fallback default
- **Overall confidence score** — already exists in `job.confidence_score`. Becomes a display-only signal, never a gate.
- **Always schedule.** Every job that passes basic validation (has images, has category, has price) gets scheduled on eBay. Schedule window is a global setting (default: 7 days out).
- **Only truly broken jobs fail.** `failed` status reserved for: API errors, no images, unrecoverable problems.

### 2. Dashboard — Confidence Triage Board

**New filter tabs:** Inbox | Processing | Scheduled | Completed | Failed

The **Scheduled** tab is the primary post-processing view:
- Sorted by confidence score (lowest first)
- Each card shows:
  - Thumbnail, title, price
  - Confidence badge — green (90%+), yellow (70-89%), red (<70%)
  - Low-confidence fields count — e.g., "3 specifics need review"
  - Days until live — "Goes live in 5 days"
  - Direct "Edit on eBay" link
- No "Action Needed" tab — that concept is gone.

**Dashboard header:** `"8 scheduled · 2 need review (< 70%) · 14 listed this week"`

### 3. Item Detail — Confidence Breakdown

When tapping a scheduled item:
- **Confidence summary card** at top — overall score with color bar
- **Item specifics list** with per-field confidence dots:
  - Green dot = confirmed from data
  - Yellow dot = AI-inferred
  - Red dot = guessed
- **"Edit on eBay" button** — prominent primary action
- **"View Listing" link** — secondary action
- **No local editing of specifics** — eBay is the editor. Dashboard is for triage only.

### 4. Settings Simplification

Under the Automation tab:
- **Schedule Window** — "Schedule listings X days from now" (default: 7, range: 1-21). Replaces per-item datetime picker.
- **Low Confidence Alert** — "Highlight items below X%" (default: 70). Controls color coding, not gating.
- **Remove:** AUTO_PUBLISH toggle, CONFIDENCE_THRESHOLD as gate, AUTO_PUBLISH_MIN_PRICE as gate, per-item datetime picker, "Process Now" manual approve button, Review tab.

### 5. Status Model Simplification

| Current (9 statuses) | New (5 statuses) |
|---|---|
| pending | pending — in inbox, waiting to process |
| processing | processing — AI pipeline running |
| scheduled, needs_review, pending_review | scheduled — on eBay, waiting to go live |
| completed | completed — listing is live |
| failed | failed — actual error |
| paused, skipped | removed |

### 6. eBay Deep Links

On successful `AddFixedPriceItem`, store the eBay Item ID and construct:
- **Edit:** `https://www.ebay.com/listing/edit?itemId={item_id}`
- **View:** `https://www.ebay.com/itm/{item_id}`

Both shown on item cards. On mobile, these open in the eBay app via URL handlers.

## What Gets Removed

- `needs_review` / `pending_review` statuses and all code paths that route to them
- "Action Needed" / "Review" tabs
- Local item specifics editing forms
- Per-item datetime picker
- AUTO_PUBLISH on/off toggle
- Confidence and min-price gating logic
- `paused` and `skipped` per-item statuses

## What Gets Added

- Per-field confidence tracking in AI pipeline
- Global schedule window setting
- Confidence-sorted Scheduled tab with eBay deep links
- Confidence breakdown in item detail view
- Simplified 5-status model

## Success Criteria

- Zero items stuck in review. Every processable item reaches eBay.
- User can identify which scheduled items need attention in < 10 seconds.
- One tap from dashboard to eBay's listing editor.
- Settings page has fewer controls, not more.
