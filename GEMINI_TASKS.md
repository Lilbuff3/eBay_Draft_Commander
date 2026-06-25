# Gemini Work Order — eBay Draft Commander

Written for a cold start. You have no memory of the prior session; everything you need is here.

## Current state (as of 2026-06-23)

- Branch `master` is current and pushed. Latest commit `5de6cc7`
  (`fix(ai): robust JSON extraction from Gemini responses`).
- The WhatsApp → Hermes → Draft Commander → eBay pipeline **works end-to-end right now.**
  Multi-photo capture, smart pricing, DST handling, persistent service, and robust AI-response
  JSON parsing are all shipped and verified live.
- DC backend runs detached as PID-of-the-moment via `pythonw backend/wsgi_service.py` on port 5000.
- Full unit suite: **409 passing.** Run with `pytest tests/unit -v`.

## HARD CONSTRAINTS — read before touching anything

1. **Do NOT touch these paths.** They are live and being used over real WhatsApp; editing them
   silently breaks capture until a *gateway* restart, and collides with active testing:
   - `integrations/hermes/**`
   - `%LOCALAPPDATA%\hermes\**` (plugin install, `config.yaml`)
2. **Work on a branch, not master.** Use `feature/listing-quality`. Branch off `master`.
   Commit each item separately. Push the branch. **Do NOT merge to master** — leave it for review.
3. **TDD every change.** Write a failing test first, watch it fail, then write minimal code to pass.
   No production code without a failing test first. Run `pytest tests/unit -v` after each item.
4. **Never edit `.env` directly** (a PreToolUse hook blocks it). Use the SettingsManager/API if needed.
5. The running DC does **not** hot-reload Python. Your edits are inert until DC is restarted —
   so editing while the user uses the tool is safe. Do not restart DC yourself.

## Why these tasks

These are listing-quality issues observed across real runs. The pipeline is reliable now;
these make the *output* better (correct specifics, stable results, no junk values).

---

## Task 1 — AI vision nondeterminism (highest value)

**Problem:** the same photo yields different Brand / Department / Type across runs.
Vision temperature is already 0.1 in `analyze_item` (`backend/app/services/ai_analyzer.py:159`),
but the prompt is loose. Tighten the prompt for deterministic, schema-pinned extraction.

- **Files:** `backend/app/core/prompts.py` (`EBAY_LISTING_PROMPT`), `backend/app/services/ai_analyzer.py`.
- **Do:** make the prompt demand exact field names, forbid guessing, and require an explicit
  `"unknown"`/null when a value isn't visible (rather than inventing one). Keep temperature ≤ 0.1.
- **Test:** a unit test (mock the client, as `tests/unit/test_ai_validation.py` does) asserting that
  given a fixed model response the parsed fields are stable and that missing values come back as
  null/unknown, not fabricated.

## Task 2 — Department gender default is wrong

**Problem:** apparel items default Department to "Women" at confidence 0.00 when the resolver can't
find a value — even when the title/identification says men's. This is the *same class* of bug as the
already-fixed Size bug.

- **Reference the fix pattern:** `processor_service._backfill_aspects_from_text` already backfills
  Size/Color/Department from the title before the resolver runs
  (`backend/app/services/processor_service.py`; see `_match_ngram_value` and the size branch, and
  `tests/unit/test_aspect_backfill.py` for the test style).
- **Do:** backfill Department from AI `identification` data (gender/target-audience cues) BEFORE the
  resolver falls back to a confidence-0 "Women" guess. If genuinely unknown, leave it unset rather
  than guessing.
- **Test:** add cases to `tests/unit/test_aspect_backfill.py` — a men's title → Department "Men";
  an ambiguous title → Department absent (no confidence-0 guess).

## Task 3 — Optional-aspect over-fill

**Problem:** n-gram backfill populates decorative *optional* aspects (e.g. Character=Blue,
Theme=Classic) with low-confidence matches, producing junk specifics.

- **File:** `backend/app/services/processor_service.py` (the backfill path that iterates aspects).
- **Do:** restrict title/n-gram backfill to aspects marked `isRequired: true`. Optional aspects
  should only be filled from research/identification data, never from loose title token matching.
- **Test:** an optional aspect with allowed values present in the title is NOT auto-filled; a
  required aspect still is.

## Task 4 — Hygiene (small, low-risk)

- **Preview endpoint info leak:** `backend/app/blueprints/api/jobs_api.py` — the `/job/<id>/preview`
  handler echoes exception text into the returned HTML on error. Return a generic message; log the
  detail server-side instead.
- **`.gitignore`:** add `data/commander.db`, `captures/`, `.playwright-mcp/` (currently untracked /
  noisy in `git status`). Confirm `commander.db` isn't meant to be tracked before ignoring; if it's
  already tracked, leave the tracked file but stop tracking future churn only if the user agrees.
- **Tests:** a request that triggers the preview error path returns no raw exception string.

---

## When done

- `pytest tests/unit -v` green (currently 409; your new tests add to that).
- Each task is its own commit on `feature/listing-quality`.
- Push the branch. Do **not** merge to master. Leave a one-line summary per commit for review.
- The user or Claude will review the diff and restart DC to activate.
