# Improvement Plan — eBay Draft Commander

Standing, tiered backlog. Authored 2026-07-17 from live app state + this week's code reviews.
Owner: Adam. Executors: Gemini (Antigravity) or Claude Code — any task block below is self-contained.

## How to use this doc

- **One task = one session = one branch.** Copy a single task block into the agent, prefixed by the standing kickoff instructions (`AGENTS.md` / `GEMINI.md` carry the hard rules).
- Definition of done inherits from AGENTS.md: tests green, frontend built if touched, backend restarted if touched, committed AND pushed.
- When a task lands: check it off here (edit this file in the same PR/commit) and close its GitHub issue if one exists.
- New ideas: file a GitHub issue first (`gh issue create`, labels per `docs/agents/triage-labels.md`), add here second.
- Priorities: P0 = money/ops now, P1 = pricing-accuracy moat, P2 = UX polish, P3 = hygiene. Within a tier, top to bottom.

Live-state snapshot that set these priorities (2026-07-17): autopilot dry-run holding **80 markdowns / 29 offers / 5 relists**; **8/8 recent sales missing COGS** ($797.62 revenue, net unknown); Tailscale client logged out twice in one day; 93 active listings; 829 backend + 50 frontend tests green.

---

## P0 — Money sitting on the table (mostly ops, not code)

### 1. Flip autopilot from dry-run to live ⬛ [P0] [size: S] [surface: ops] — GitHub issue #81
**Problem:** Autopilot has been auditing itself in dry-run: last cycle recorded 80 markdowns, 29 offers-to-watchers, and 5 relists it *would* have made. None touched eBay. Stale inventory sits at full price.
**Files:** none (Settings → Automation), audit surface `home/TodayPanel.tsx` + `listing_actions` table.
**Approach:**
- On the Today panel (or `sqlite3 data/commander.db "select * from listing_actions order by id desc limit 30"`), spot-check ~10 dry-run rows: markdown floors respected (`MARKDOWN_FLOOR_PCT` 70 / discovery 40), offer discounts sane, no absurd drops.
- If sane: Settings → Automation → `OFFERS_MARKDOWNS_DRY_RUN=false`, restart backend.
- Watch the next daily cycle's WhatsApp digest.
**Verify:** `GET /api/today` shows `dry_run: false` after restart; next cycle writes live `listing_actions` rows; offers visible in eBay Seller Hub.

### 2. Backfill missing COGS on ledger sales ⬛ [P0] [size: S] [surface: ops] — GitHub issue #82
**Problem:** All 8 recent sales lack cost basis, so the Profit tab reports $0 net on $797.62 revenue — the ledger feature works, the data loop doesn't.
**Files:** none (Profit tab UI → `POST /api/ledger/sales/<order_id>/cogs`).
**Approach:** Profit tab → amber "add cost" fill-ins on each sale. Going forward: include `paid X` in WhatsApp capture captions (parsed + stripped automatically) or set `cogs` at Sourcing "Bought" time.
**Verify:** `GET /api/ledger/summary?weeks=4` → `missing_cogs: 0`, `net` non-zero.

### 3. Fix Tailscale for good + finish phone PWA install ⬛ [P0] [size: S] [surface: ops]
**Problem:** Tailscale v1.98.9 logged itself out twice in one day; every logout kills the HTTPS URL, which blocks the phone PWA install (the "no Chrome bar" experience) and the camera barcode scanner.
**Approach:**
- Reinstall the current Tailscale client from tailscale.com/download (twice-daily logout is not normal). Sign in once.
- Confirm `tailscale serve status` shows the port-5000 proxy (auto-restores from tailscaled state; if empty: `tailscale serve --bg 5000`).
- Reboot the PC once; confirm login + serve survive.
- Phone: Tailscale app ON → Chrome → `https://tuf-2.taile466a6.ts.net/app/` → ⋮ → Add to Home screen → **Install** → launch from the icon.
**Verify:** app opens full-screen from home-screen icon (no browser bar); camera scanner works on the Sourcing tab.

### 4. Calibrate ACTIVE_TO_SOLD_FACTOR from real sales ⬛ [P0] [size: S] [surface: ops]
**Problem:** Every comp-based price is discounted by a guessed 0.87; the app now has enough real sold orders to measure the true ratio.
**Files:** `tools/accuracy_benchmark.py` (exists), Settings → Automation.
**Approach:** `"C:\Program Files\Python312\python.exe" tools/accuracy_benchmark.py --suggest-factor` (uses live Orders API; respects the n<25 small-sample warning — if n<25, note the suggestion and re-run monthly instead of applying). If suggested factor differs from 0.87 by >0.03 and n is adequate, update in Settings + restart.
**Verify:** benchmark report printed; `GET /api/settings` shows the new factor; next comp-priced job's reasoning line reflects it.

---

## P1 — Pricing accuracy moat

### 5. Own-sales comp source (strategy 0.5 in the cascade) ⬜ [P1] [size: M] [surface: backend+frontend]
**Problem:** The strongest possible price signal — "you sold this exact item before, for $X" — is sitting unused in the `sales` table.
**Files:** `backend/app/services/pricing_engine.py` (`get_price_with_comps`), `backend/app/services/ledger.py` (new query helper), `backend/app/services/listing_ai_agent.py` (projection — the seam test enforces threading), `frontend/src/components/item-detail/PriceExplainer.tsx`.
**Approach:**
- Ledger helper: `get_own_sold_prices(isbn=None, mpn=None)` → join `sales` → `jobs` on `job_id`, match identifier from job `ai_json` identification; return `[{price, sold_at, title}]`.
- New cascade step before ISBN search: if own sales exist for the identifier, price from their median (recent-weighted if >3), `source='own_sales'`, `confidence='high'`, reasoning "You sold this N time(s), last at $X on <date>". Still add the shipping buffer.
- Thread any new return fields through `get_final_pricing`'s projection (`tests/unit/test_pricing_projection_seam.py` fails on drops) and persist in `processor_service`.
- PriceExplainer: when `source == 'own_sales'`, green banner "You sold this for $X on <date>" above the comp cards.
**Verify:** new unit tests in `test_pricing_engine.py` (own-sale hit short-circuits Browse call — mock `search_sold_listings`, assert not called) + `test_ledger.py` (helper join). Full suite green. Manual: re-run pricing on a job whose ISBN matches a past sale.

### 6. Range-bar vs comp-cards consistency ⬜ [P1] [size: S] [surface: backend]
**Problem:** `calculate_suggested_price` grade-filters comps internally (`prefer_same_grade_comps`) before computing `median_price`/`price_range`, but the top-5 comps returned for display are pre-filter — a displayed card's price can sit outside the explainer's labeled min/max.
**Files:** `backend/app/services/pricing_engine.py` — `calculate_suggested_price` (~line 405) and the market-path returns in `get_price_with_comps`.
**Approach:** have `calculate_suggested_price` also return the grade-filtered list (e.g. `"comps_used"`); market paths return `comps_used[:5]` as `comps` when grade filtering fired, else the existing slice. Don't change `median_price` semantics.
**Verify:** unit test: comps mixing Excellent+Acceptable grades with our condition Excellent → returned display comps all within returned `price_range`. Full suite green.

### 7. Apply for eBay Marketplace Insights API ⬜ [P1] [size: S] [surface: external]
**Problem:** Real sold-comp data (90-day sold history) is gated behind eBay's limited-release approval; the app currently approximates with active×factor. Probe on 2026-07-17 confirmed the app keys are NOT granted the scope.
**Approach:** developer.ebay.com → account → Application Growth Check / API access request → request `buy.marketplace.insights` for the production keyset; business justification: owner-seller pricing own inventory. Expect weeks; individual sellers often rejected — file and forget.
**Verify:** re-run the scope probe (client-credentials token request with the insights scope) — HTTP 200 instead of 400. If granted, file a new P1 task to wire `item_sales/search` in behind `search_sold_listings`.

### 8. Sourcing comp thumbnails ⬜ [P1] [size: S] [surface: frontend]
**Problem:** The Source tab's buy/pass verdict shows comp titles/prices but no photos; `/api/lookup/comps` already returns `image_url` per comp (added 2026-07-17, unused). Seeing the comps' photos = instant confidence the match is the right product.
**Files:** `frontend/src/pages/Sourcing.tsx` (comp list render ~line 164, comps type ~line 38).
**Approach:** add `image_url?: string` to the comps type; render a 40px rounded thumb before the title (fallback: hide img on error — copy the `CompThumb` pattern from `PriceExplainer.tsx`). Keep the list at 5.
**Verify:** `npx vitest run` green; `npm run build`; scan a known ISBN on the Source tab → thumbnails visible.

---

## P2 — UX / confidence polish

### 9. Price explainer in the Review Queue ⬜ [P2] [size: S] [surface: frontend]
**Problem:** The review queue is exactly where price justification matters (jobs stop there *because* of price flags), but it shows only the flag reason — the comp evidence lives one tab away.
**Files:** `frontend/src/components/listings/ReviewQueue.tsx`; reuse `item-detail/PriceExplainer.tsx` as-is (already standalone; takes `pricing` + `price`).
**Approach:** ReviewQueue cards fetch job details (check what it already loads); render `<PriceExplainer pricing={details.pricing_data} price={job.price}>` collapsed behind a "Why this price?" disclosure to keep cards compact. NOTE: ReviewQueue is a lazy tab — importing PriceExplainer there is fine (both non-eager), but never import ReviewQueue into eager code.
**Verify:** flag a job into review (or use an existing `pending_review`), open Review tab → explainer renders with comps; build + vitest green.

### 10. Component tests for the stateful UI ⬜ [P2] [size: M] [surface: frontend]
**Problem:** The two most stateful new components — `PriceExplainer` (range math/clamping/fallbacks) and `MobileCaptureSheet` (capture⇄success phase machine, sticky condition, session counter) — have zero test coverage; regressions there are silent.
**Files:** new `frontend/src/components/item-detail/PriceExplainer.test.tsx`, `frontend/src/components/MobileCaptureSheet.test.tsx`. May need `@testing-library/react` added to devDependencies (vitest + jsdom already configured — check `vite.config.ts` test block first).
**Approach:**
- PriceExplainer: renders null with no comps+range; marker positions clamp 0–100%; old-job shape (comps without image_url, null range) renders cards without bar; low-confidence banner shows reason.
- MobileCaptureSheet: mock `onUpload` resolve → phase flips to success, counter increments, condition survives "Snap next item"; reject → stays in capture with photos intact.
**Verify:** `npx vitest run` — new tests green, count rises from ~50.

### 11. On-device momentum-loop pass ⬜ [P2] [size: S] [surface: ops] — after task 3
**Problem:** The capture momentum loop (success interstitial, one-tap next item, haptics) shipped verified by emulation only — never felt on the actual phone.
**Approach:** with the PWA installed (task 3), list 3 real items back-to-back. Note friction: interstitial timing, haptic strength, camera-launch speed, condition stickiness. File small follow-up issues for anything that grates.
**Verify:** 3 real listings created via the loop; follow-ups filed or "feels right" noted here.

---

## P3 — Hygiene / debt (batch into one session)

### 12. Silent exception handler sweep ⬜ [P3] [size: M] [surface: backend]
**Problem:** Prior review (memory obs #1468) flagged swallowed exceptions hiding real errors.
**Files:** `backend/app/**` — find with `grep -rn "except.*: pass\|except Exception" backend/app --include="*.py"`.
**Approach:** classify each: intentionally failure-safe paths (WhatsApp notify, promotion hook, ledger best-effort sweep — documented as such) keep swallowing but must log at debug/warning; anything else gets narrowed exception types + logging. No behavior changes beyond logging.
**Verify:** full pytest green; grep shows no bare `except: pass` without a log call.

### 13. Eventlet exit decision ⬜ [P3] [size: L] [surface: backend]
**Problem:** eventlet is deprecated upstream (memory obs #1464); the app pins it for Flask-SocketIO async mode. One-user app likely fine on `async_mode='threading'`.
**Approach:** spike branch: switch `async_mode` to threading in `app/__init__.py` + drop eventlet monkey-patching in `wsgi*.py`; run the full manual smoke (`draft-commander-test` skill): queue run, Socket.IO live updates on the dashboard, restart supervisor cycle. Long-lived uploads + background threads are the risk areas.
**Verify:** live queue processes a real job end-to-end with real-time updates; `/api/system/restart` cycle works. DO NOT merge on tests alone — needs the live proof.

### 14. Regenerate stale nested AGENTS.md files ⬜ [P3] [size: S] [surface: docs]
**Problem:** `backend/AGENTS.md`, `frontend/AGENTS.md`, etc. date from 2026-03; root AGENTS.md was refreshed 2026-07-17 but children still describe March architecture.
**Approach:** either regenerate with the original tool, or trim each to a 5-line pointer ("read root AGENTS.md + CLAUDE.md; this dir = <one paragraph>"). Pointers preferred — less to go stale.
**Verify:** `grep -rl "244" */AGENTS.md` → no hits; no dead file references.

### 15. CLAUDE.md split watch ⬜ [P3] [size: — ] [surface: docs]
**Problem:** CLAUDE.md is ~300 lines of paragraph-dense bullets; past ~350 it stops being scannable.
**Approach:** when it crosses ~350 lines, move per-feature deep detail into `docs/` (CONTEXT.md convention already documented in CLAUDE.md "Domain docs") keeping one-line pointers. Not yet — just don't let bullets grow unbounded.
**Verify:** n/a (tripwire task).

---

## Changelog
- 2026-07-17: created. P0.1/P0.2 filed as GitHub issues.
