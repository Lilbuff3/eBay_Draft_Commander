# Improvement roadmap for eBay Draft Commander

## 0. How to use this doc
- One task = one session/branch. Copy the task block into Gemini/Claude, prefixed by the standing kickoff instructions (AGENTS.md / GEMINI.md).
- Definition of done inherits from AGENTS.md hard rules (tests green, build, restart, push).
- When a task lands: check it off here + close its GitHub issue if one exists. New ideas → GitHub issue first, doc second.

## P0 — Money sitting on the table (do first, mostly ops not code)

### 1. Flip autopilot live [P0] [size: S] [surface: ops]
Problem: Autopilot is still in dry-run with real money parked behind the flip.
Files: none (config)
Approach:
- Audit the dry-run `listing_actions` rows (80 markdowns / 29 offers / 5 relists) on the Today panel.
- Spot-check ~10 for sanity (floors respected, no absurd drops).
- Set `OFFERS_MARKDOWNS_DRY_RUN=false` in Settings → Automation + restart.
Verify: next cycle's digest text + `listing_actions` live rows; eBay Seller Hub shows the offers.
Issue: #83

### 2. Backfill the 8 missing COGS [P0] [size: S] [surface: ops]
Problem: Profit ledger is blind because 8 recent sales have `missing_cogs` causing net to show $0.
Files: none (UI)
Approach:
- Use the Profit tab amber "add cost" fill-ins (`POST /api/ledger/sales/<order_id>/cogs`) for the 8 missing COGS.
- Adopt the habit: `paid X` in WhatsApp captions moving forward.
Verify: `/api/ledger/summary` net ≠ 0.
Issue: #84

### 3. Fix Tailscale for good [P0] [size: S] [surface: ops]
Problem: Tailscale client logged out twice in one day (v1.98.9), killing phone HTTPS and PWA install.
Files: none (system)
Approach:
- Reinstall current client.
- Confirm `tailscale serve status` persists across a reboot.
- Complete the phone PWA install (docs/ANTIGRAVITY.md §quirks + prior session steps).
Verify: standalone app on phone, no Chrome bar.

### 4. Run the factor calibration [P0] [size: S] [surface: ops]
Problem: ACTIVE_TO_SOLD_FACTOR needs to be calibrated against actual sales.
Files: `tools/accuracy_benchmark.py`
Approach:
- Run `python tools/accuracy_benchmark.py --suggest-factor` against real sold orders (n≥25 warning respected).
- Update `ACTIVE_TO_SOLD_FACTOR` in Settings if it moves >0.03.
Verify: benchmark report; new listings priced with updated factor.

## P1 — Pricing accuracy moat (code, ordered by leverage)

### 5. [x] Own-sales comp source [P1] [size: M] [surface: backend/frontend]
Problem: Past sales of the same identifier aren't being used as a high-confidence pricing anchor.
Files: `backend/app/services/pricing_engine.py`, `backend/app/core/ledger.py`, `frontend/src/components/item-detail/PriceExplainer.tsx`, `backend/app/services/listing_ai_agent.py`
Approach:
- New step in pricing cascade before Browse comps: query `sales` table (join jobs on ISBN/MPN) for own past sales.
- If found, use actual sold price as high-confidence anchor (source `own_sales`, confidence high).
- Surface in price explainer as "You sold this for $X on <date>".
- Thread through `get_final_pricing` projection (seam test will enforce).
Verify: `tests/unit/test_pricing_engine.py` + `test_ledger.py` extended and passing.

### 6. [x] Range-bar/comp-cards consistency [P1] [size: S] [surface: backend]
Problem: `calculate_suggested_price` grade-filters internally but displays top-5 pre-filter comps, causing mismatch with the range bar.
Files: `backend/app/services/pricing_engine.py`
Approach:
- Return the grade-filtered list for display when filtering fired (or annotate it).
Verify: Displayed comp cards match the range bar calculation.

### 7. Apply for Marketplace Insights [P1] [size: S] [surface: ops]
Problem: eBay Marketplace Insights API access is needed for real sold comps.
Files: none
Approach:
- File the limited-release access request on the eBay developer portal.
- No code until granted.
Verify: Request submitted on developer portal.

### 8. [x] Sourcing comp thumbnails [P1] [size: S] [surface: frontend]
Problem: `/lookup/comps` returns `image_url` but the Sourcing comp list doesn't display them, missing a visual confirmation opportunity.
Files: `frontend/src/pages/Sourcing.tsx`
Approach:
- Render 40px thumbs in the Sourcing comp list (type at line ~38).
- Use `image_url` from the comps payload.
Verify: Visual confirm that comps match the scanned item in the UI.

## P2 — UX / confidence polish

### 9. [x] Price explainer in ReviewQueue [P2] [size: S] [surface: frontend]
Problem: The pending-review card lacks price justification context where it's needed most.
Files: `frontend/src/components/listings/ReviewQueue.tsx`
Approach:
- Embed the `PriceExplainer` component under the review reason.
Verify: Price explainer renders correctly inside ReviewQueue cards.

### 10. [~] Component tests for the stateful UI [P2] [size: M] [surface: frontend]
Problem: Missing tests for stateful UI pieces (`PriceExplainer` and `MobileCaptureSheet`).
Files: `frontend/src/components/item-detail/PriceExplainer.test.tsx`, `frontend/src/components/listings/MobileCaptureSheet.test.tsx`, `frontend/src/components/listings/ReviewQueue.test.tsx`
Approach:
- Write @testing-library/react + jsdom tests for `PriceExplainer` (range math, clamping, states).
- Write tests for `MobileCaptureSheet` phase machine (capture⇄success, sticky condition, counter).
- ReviewQueue + CompactPriceExplainer covered (`ReviewQueue.test.tsx`); PriceExplainer/MobileCaptureSheet unit tests still open.
Verify: `npx vitest run` passes with new tests.

### 11. Momentum-loop analytics sanity [P2] [size: S] [surface: ops/frontend]
Problem: Capture interstitial flow needs on-device verification and tuning.
Files: `frontend/src/components/listings/MobileCaptureSheet.tsx` (potentially)
Approach:
- Verify the capture interstitial's flow on-device once PWA install works (P0.3).
- Adjust copy/timing from real use.
Verify: Smooth on-device experience without jarring transitions.

## P3 — Hygiene / debt (batch into one session)

### 12. [x] Silent exception handlers sweep [P3] [size: S] [surface: backend]
Problem: Memory obs #1468 identified swallowed exceptions hiding real errors.
Files: `backend/app/**/*.py`
Approach:
- Grep `except.*pass` or bare `except Exception` without logging in `backend/app`.
- Add logging or narrow exceptions.
- Keep best-effort paths (WhatsApp notify, promotion) failure-safe.
Verify: No bare/silent exceptions remain except in intentional best-effort paths.

### 13. Eventlet migration decision [P3] [size: M] [surface: backend]
Problem: Eventlet is deprecated (obs #1464).
Files: `backend/wsgi.py`, `backend/app/__init__.py`, `backend/requirements.txt`
Approach:
- Spike branch: evaluate moving SocketIO async_mode to `threading`.
- Full manual smoke via `draft-commander-test` skill.
Verify: Live queue-run proof before merging.

### 14. [x] Nested AGENTS.md regeneration [P3] [size: S] [surface: docs]
Problem: `backend/AGENTS.md` and others are from March and likely stale.
Files: `backend/AGENTS.md`, `frontend/AGENTS.md`, `tests/AGENTS.md`, `templates/AGENTS.md`, `scripts/AGENTS.md`, `tools/AGENTS.md`, `docs/AGENTS.md`
Approach:
- Regenerate or trim these files to pointers to the root AGENTS.md / CLAUDE.md.
Verify: Subdirectory AGENTS.md files are current or point to root.

### 15. CLAUDE.md split watch [P3] [size: S] [surface: docs]
Problem: `CLAUDE.md` is ~350 lines and growing.
Files: `CLAUDE.md`, `docs/*.md`
Approach:
- Move per-feature deep detail into `docs/`.
- Keep one-line pointers in `CLAUDE.md` per CONTEXT.md convention.
Verify: `CLAUDE.md` is more concise, details preserved in `docs/`.
