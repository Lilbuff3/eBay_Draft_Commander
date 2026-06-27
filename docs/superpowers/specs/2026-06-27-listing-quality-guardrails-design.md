# Listing-Quality Guardrails — Design Spec

**Date:** 2026-06-27
**Branch:** `feature/listing-quality-guardrails`
**Status:** Approved design, pending implementation plan

## Summary

A review of 24 scheduled listings surfaced four recurring quality problems:
duplicate listings, a wildly wrong price ($1091.99 vintage shears), bad brand
values ("Signed", "Disney / Chronicle Books"), and malformed titles
("...(Alkaline,", repeated words). All trace to **one missing layer**: there is no
listing-quality guardrail between AI/pricing output and eBay submission. The
pipeline largely trusts the AI and applies only thin validation
(`validate_title` rejects >80 chars; `_sanitize_price` clamps to a flat
[$4.99, $9999.99]).

This adds that layer: a single `listing_guardrails` module with four checks that
either **auto-fix** safe issues or **route the job to review** for judgment calls.

## Root causes (confirmed in code)

| Problem | Root cause |
|---------|-----------|
| Duplicates | Dedup is folder-name-only (`scanner_service.py:61` `get_job_by_folder`). Each WhatsApp send is a new uuid folder, so the same item re-sent creates a second job. No item-identity dedup. |
| $1091.99 price | `_sanitize_price` only clamps to flat [$4.99, $9999.99] (`pricing_engine.py:98`). No category/comp-relative sanity. |
| Bad brand values | AI vision's brand used verbatim — no blocklist, no `/`-split, no normalization. |
| Malformed title | `validate_title` only rejects >80 chars (`validator.py:45`); never cleans. AI self-truncates at its 80-char budget → dangling fragment ships as-is. |

## Decisions (locked during brainstorming)

| Decision | Choice |
|----------|--------|
| Scope | All 4 guardrails: duplicate, price sanity, title hygiene, brand/aspect |
| Handling | **Smart split** — auto-fix title + brand (proceed); route duplicate + price-outlier to review |
| Dedup method | **Perceptual photo-hash (dHash)** — conservative; different photos never trip, so legit variants/multiples are safe |
| Dedup action | Flag for review only — never auto-block (user lists intentional variations) |
| Price outlier | **Both signals** — (a) no-market-data source AND > threshold, OR (b) > ~3× comp median |
| Review mechanism | Reuse existing `pending_review` status; reason in `error_message` |

## Architecture — one layer, two hook points

Dedup runs **early (at capture)** so a re-send is caught before a wasted ~60s
Gemini call. Title/brand/price run **late (before eBay submit)**.

```
WhatsApp capture -> /api/capture
  └─ GUARD: photo-hash dedup -> near-match to recent? -> status=pending_review
       ("possible duplicate of <id>"), SKIP AI processing
  └─ else: store photo hashes on the job, process normally
       AI analysis -> pricing -> specifics enrichment
       └─ GUARD: title hygiene   (auto-fix the title)
       └─ GUARD: brand/aspect    (auto-fix aspect values)
       └─ GUARD: price sanity    (outlier -> status=pending_review; else proceed)
            └─ create_listing (eBay Trading API)
```

## Components

### New: `backend/app/services/listing_guardrails.py`
Pure, dependency-light functions (Pillow already present; no new deps):

- `compute_photo_hashes(image_paths) -> list[str]` — perceptual **dHash** per image
  via Pillow (grayscale, resize 9x8, compare adjacent pixels → 64-bit hex). No new
  dependency.
- `find_duplicate(new_hashes, recent_jobs, max_distance) -> Optional[dict]` —
  returns the matching job (id/listing_id) if any new hash is within
  `max_distance` Hamming distance of a stored hash; else None.
- `clean_title(title) -> str` — strip dangling trailing punctuation/fragments
  (e.g. trailing `(`, `,`, unbalanced `(...,`), collapse consecutive/duplicate
  words case-insensitively, normalize whitespace, ensure ≤80 and no mid-word cut.
- `normalize_aspects(specs: dict) -> dict` — for Brand and similar identity
  aspects: map blocklisted non-brands (e.g. "Signed", "Various", "N/A") to
  "Unbranded"; split `"A / B"` to the first meaningful value; drop empty/junk.
- `check_price_sanity(price, source, comps) -> Optional[str]` — returns a review
  reason string if (a) `source` is a no-market-data source
  (`ai_grounded_research`, `ai_estimate`/vision fallback) AND
  `price > PRICE_REVIEW_THRESHOLD`, OR (b) comps exist and
  `price > PRICE_COMP_MULTIPLE * median(comp prices)`. Else None.
- `apply_pre_listing_guardrails(job) -> GuardrailResult` — orchestrates the LATE
  guards: mutates title/aspects in place (auto-fix), runs price sanity, returns
  `{review_reason: Optional[str]}`.

### Modified
- `backend/app/blueprints/api/queue_api.py` (`capture_item`): after staging,
  compute photo hashes; run `find_duplicate` against recent jobs; if matched,
  create the job but set `pending_review` + reason and do NOT start processing.
  Otherwise store `job_metadata['photo_hashes']` for future comparison.
- `backend/app/services/processor_service.py` (before `create_listing`): call
  `apply_pre_listing_guardrails`; if it returns a `review_reason`, set the job to
  `pending_review` with that reason instead of listing.
- `backend/app/core/constants.py`: thresholds + brand blocklist (see Config).

## Configuration (env, tunable)
- `DUP_HASH_DISTANCE` (default 6) — max Hamming distance for a photo "match".
- `DUP_LOOKBACK_DAYS` (default 30) — how far back to compare hashes.
- `PRICE_REVIEW_THRESHOLD` (default 150.0) — no-comp prices above this → review.
- `PRICE_COMP_MULTIPLE` (default 3.0) — price above this × comp median → review.
- `BRAND_BLOCKLIST` — non-brand tokens normalized to "Unbranded" (e.g. Signed,
  Various, N/A, Unknown).

## Data / storage
- Photo hashes live in `job_metadata['photo_hashes']` (a list of hex strings) —
  follows the existing capture-hint pattern; no schema change.
- Dedup comparison queries recent jobs (within `DUP_LOOKBACK_DAYS`) whose
  `job_metadata` carries `photo_hashes`.

## Error handling
- Guardrails are best-effort: any guardrail that raises is caught and logged, and
  the job proceeds (a guardrail must never block a listing by crashing). The only
  intentional "block" is routing to `pending_review`.
- Auto-fix guardrails are idempotent and no-op on already-clean input.

## Safety properties
- **Variants protected:** photo-hash dedup only trips on near-identical *photos*,
  so intentionally-similar variant listings (different photos) never flag.
- **No-op on clean input:** clean titles/aspects/prices pass through unchanged.
- **Early dedup saves cost:** a detected re-send skips AI entirely.

## Testing (TDD)
`tests/unit/test_listing_guardrails.py`:
1. `clean_title`: dangling `"(Alkaline,"` cleaned; `"Sencore … Sencore"` deduped;
   already-clean title unchanged; never exceeds 80.
2. `normalize_aspects`: "Signed"→"Unbranded"; "A / B"→"A"; valid brand unchanged.
3. `check_price_sanity`: no-comp $1091 → review reason; comp-backed normal price →
   None; price > 3× comp median → review; under threshold → None.
4. `compute_photo_hashes` + `find_duplicate`: identical image → distance 0 (flag);
   visibly different images → distance > threshold (no flag); empty/missing → no
   crash.
5. No-op paths: each guardrail returns clean/None for good input (no false trips).

## Out of scope (v1)
- Re-photographed duplicates (different photos of the same item) — photo-hash
  won't catch these; identifier-based dedup was explicitly rejected to protect
  variants.
- Auto-repricing outliers (we route to review, not auto-correct).
- Frontend changes beyond what `pending_review` already surfaces.

## Deploy
- Backend-only; activate by restarting DC (no Hermes gateway restart needed —
  `capture_to_dc.py` is unaffected). Per-task commits on
  `feature/listing-quality-guardrails`; merge after review.
