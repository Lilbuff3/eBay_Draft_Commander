# No-Blocks Listing Engine — Design

Date: 2026-06-15
Status: Approved (brainstorm) → ready for implementation plan
Scope: Piece 1 of the "capture-and-forget" product reframe (foundation)

## Context / Why

The app's whole value is supposed to be: photograph an item, walk away, it gets listed on eBay. Today the back half breaks that promise. After the AI runs, items frequently land in a **review queue** because eBay requires category-specific item specifics (Size, Color, Department, etc.) that the AI didn't fill. The user must then open each item's editor, hand-fill the missing fields past a disabled "Missing Required Specifics" gate, and submit — one item at a time.

The user's insight: **there should be no blocking mistakes, ever.** The listing is going out as a scheduled/editable listing anyway — low stakes. Any missing required value can be *searched, reasoned, or guessed* (via Gemini or eBay's own data) and filled automatically. If it truly can't be determined, a safe default is fine; it's still just a draft/scheduled listing — no harm. Forcing the human to type a value the system could infer is pure friction and the root reason the app "feels off."

This spec covers the **engine** that makes blocking impossible. It's the foundation the rest of the reframe builds on.

## Product north star (context for the whole reframe)

The app becomes **tap category → pick condition → snap photos → walk away → check your scoreboard.** No editor in the happy path. Four sequenced pieces:

1. **No-blocks engine** (this spec) — required aspects are always auto-resolved; jobs never stall on missing data.
2. **Category-first capture** — four capture cards (Clothing, Shoes, Electronics, Books & Media); each opens only a category-tuned condition picker, then photos → submit.
3. **Scoreboard** — Home page showing money made, time saved, total listed value.
4. **Inventory** — in-app view of live/scheduled/sold listings.

Pieces 2–4 are **out of scope** here; this spec is Piece 1 only.

## Current behavior (what exists today)

Pipeline: `backend/app/services/processor_service.py :: ProcessorService.process_listing()` (the long method around lines 300–620).

Aspect handling, in order:
- `_validate_and_enrich_specifics()` (processor_service.py:175) — fetches eBay required/optional aspects via `ebay/taxonomy.py::get_item_aspects`, auto-fills single-allowed-value required aspects, fuzzy-matches existing values to allowed values, returns `ebay_aspect_schema` (each aspect carries `name`, `values`, `isRequired`).
- Two-pass AI enrichment (processor_service.py:400) — `ai_analyzer.enrich_item_specifics(image_paths, title, identification, category_name, aspect_schema, existing_specifics, research_specs)` fills more from the images.
- `_backfill_aspects_from_text()` (processor_service.py:124) — fills Size/Color/Department from the title against each aspect's allowed-value list.

The **gate** — "Hybrid Publishing Logic (Phase 2 Intercept)" (processor_service.py:506–582):
- `SAFE_DEFAULT_ASPECTS = {Brand, MPN, Type, Model, UPC, EAN, Country/Region of Manufacture, California Prop 65 Warning}` → auto-filled with `"Does Not Apply"`.
- Any *other* required aspect still absent → appended to `missing_aspects`.
- Routes to `status="pending_review"` if `not user_approved and (not auto_publish or confidence < threshold or missing_category or missing_aspects)`. `missing_aspects` are persisted to `ai_data['missing_required_aspects']`.

Consumed by `queue_manager.py:887` (`pending_review` → `JobStatus.PENDING_REVIEW`) and surfaced in the frontend drawer, which disables the Create button while required specifics are empty.

Separately, the **condition gate** (processor_service.py:429) sets `status="awaiting_condition"` when condition is `None`. Category-first capture (Piece 2) will always supply condition, so this gate becomes effectively unreachable later — but this spec leaves it intact.

## Design

### Principle
After the existing enrichment passes, **no required aspect and no category may remain unresolved as a blocker.** A final resolver guarantees every required aspect holds a valid value; category falls back to a safe id. `missing_aspects` and `missing_category` are removed from the blocking condition. The only remaining reason a job waits is the *publish decision* (AUTO_PUBLISH / confidence / user tap) — and that wait now means "ready, data complete, awaiting your go," never "you must fill data." This reframes `pending_review` from a data-entry chore into a one-tap confirmation (which Piece 2 turns into list-from-card).

### New component: required-aspect resolver
Add `resolve_missing_required_aspects()` to `backend/app/services/ai_analyzer.py` (alongside `enrich_item_specifics`, reusing its Gemini client, rate limiter, and JSON-parse helpers).

Signature (shape):
```
resolve_missing_required_aspects(
    missing: list[dict],          # [{name, values:[allowed...]}] still-empty required aspects
    title, identification, category_name,
    image_paths, research_specs,
) -> dict[str, dict]              # { aspect_name: {value, confidence: 0..1, source} }
```
Behavior:
- **One batched call** for ALL missing aspects (not one-per-aspect) — cost-effective, and only invoked when `missing` is non-empty.
- Prompt instructs: for each aspect, choose the best value; **if the aspect has an allowed-value list, the answer MUST be one of those values**; return a per-aspect confidence and a one-word source (`image` / `research` / `inferred`). Allowed-value lists are passed in the prompt (already capped to 50 in `_validate_and_enrich_specifics`).
- Returns only confident, valid values; the caller applies deterministic fallback for anything the model abstains on.

### Resolver cascade (in processor_service, replacing the missing→review path)
After the existing `SAFE_DEFAULT_ASPECTS` fill, for each required aspect still missing, resolve in order — first hit wins:
1. **eBay allowed values, single/obvious** — already handled (single-value auto-fill, fuzzy match). Keep.
2. **Batched Gemini resolve** — `resolve_missing_required_aspects()`; accept values that are valid (in allowed list when constrained) and above a confidence floor (e.g. ≥0.45 — low bar on purpose; it's a draft).
3. **Deterministic safe default** — for a constrained aspect, the most common / first allowed value; for free-text, `"Unbranded"` (Brand-like) or `"Does Not Apply"`. eBay always accepts the result.

After the cascade, `missing_aspects` is empty by construction.

### Gate change
In the Phase-2 intercept:
- Remove `missing_aspects` and `missing_category` from the blocking boolean.
- **Category fallback:** if `cat_result.id` is missing, set it to the existing safe fallback category (`170599`, per project docs) and log it — never block on category.
- The remaining gate is purely the publish policy (`user_approved`, `auto_publish`, `confidence < threshold`). When it holds, status is `pending_review` but now means **"ready to list — data complete."** (Piece 2 renames/representation; this spec keeps the status string to avoid churn, but stops populating `missing_required_aspects`.)

### Provenance for the soft marker
Persist `ai_data['auto_filled_aspects'] = { name: {value, confidence, source} }` for every value the resolver/fallback produced. This drives the future quiet "N auto-filled — tap to review" marker (Piece 2). Stop writing `ai_data['missing_required_aspects']` (nothing is "missing" anymore); migrate any reader to `auto_filled_aspects`.

### Tunables (constants / env)
- `ASPECT_RESOLVE_CONFIDENCE_FLOOR` (default 0.45)
- Reuse existing Gemini model + rate limiter; no new external calls except the single batched resolve, only when needed.

## Data flow (after change)

```
enrich passes (existing) → still-missing required aspects?
   ├─ no  → gate (publish policy only)
   └─ yes → resolver cascade (allowed-values → batched Gemini → safe default)
            → all filled, provenance saved → gate (publish policy only)
category missing? → safe fallback id (never blocks)
```

## Components touched
- `backend/app/services/ai_analyzer.py` — new `resolve_missing_required_aspects()`.
- `backend/app/services/processor_service.py` — resolver cascade after SAFE_DEFAULT_ASPECTS fill; gate boolean drops `missing_aspects`/`missing_category`; category fallback; write `auto_filled_aspects`, stop writing `missing_required_aspects`.
- `backend/app/core/constants.py` — confidence floor; confirm safe fallback category id is centralized.
- `backend/app/core/prompts.py` — prompt template for the batched resolver.
- Readers of `missing_required_aspects` (frontend drawer + `JobDetails` type) — migrate to `auto_filled_aspects` (soft marker, non-blocking). Frontend Create button no longer disabled for specifics.

## Edge cases & error handling
- **Gemini call fails / times out / returns junk** → caught, fall through to deterministic safe defaults. Never blocks, never raises into the pipeline (mirror existing `try/except` around `enrich_item_specifics`).
- **Constrained aspect, model returns an out-of-list value** → rejected, fall to safe default (first/most-common allowed value).
- **Allowed-value list empty (free-text aspect)** → accept model value if confident; else `"Does Not Apply"` / `"Unbranded"`.
- **Cost** → resolver runs only when something is still missing after the cheap passes; one batched call covers all remaining aspects.
- **Value length** → respect `ASPECT_VALUE_MAX_LENGTH` (already truncated at processor_service.py:302).
- **Wrong guess on a live listing** → low harm by design (editable/scheduled); provenance marker lets the user spot-check; Piece 2 adds the optional review affordance.

## Testing
- **Unit — resolver** (`tests/unit/`): given missing aspects with/without allowed-value lists, asserts: constrained answers always in-list; abstain → deterministic fallback; Gemini exception → fallback, no raise. Mock the Gemini client (no live calls).
- **Unit — gate**: with required aspects deliberately unresolved pre-cascade, assert post-cascade `missing_aspects == []` and status is NOT forced to review by data; `missing_category` triggers fallback id, not a block; `auto_filled_aspects` populated; `missing_required_aspects` no longer written.
- **Integration** (`tests/integration/`, needs creds + sandbox): run the three fixtures `tests/fixtures/images/{boombox,cookbook,tesla-jacket}` end-to-end; assert none land in review for missing specifics and each reaches a listable state with all required aspects valued.
- **Regression**: existing aspect-enrichment / condition-mapping tests stay green.

## Out of scope (later pieces)
- Category-first capture cards + per-category condition presets (Piece 2).
- List-from-card / bulk-list / drawer demotion (Piece 2).
- Scoreboard money/time/value page (Piece 3).
- In-app inventory polish (Piece 4).
- Changing AUTO_PUBLISH/confidence *policy* itself (only its data-blocking coupling is removed here).

## Open decisions
- Confidence floor value (start 0.45; tune on fixtures).
- Whether to keep the `pending_review` status string now and rename in Piece 2, or introduce a `ready` status now. Recommendation: keep the string this spec, reinterpret in Piece 2 to avoid migration churn.
