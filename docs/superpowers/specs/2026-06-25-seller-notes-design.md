# Seller Notes — Design Spec

**Date:** 2026-06-25
**Branch:** `feature/seller-notes`
**Status:** Approved design, pending implementation plan

## Summary

Let the seller attach a free-text note when sending an item's photos via WhatsApp.
The note is **trusted seller knowledge that fills what the photos cannot show** — e.g.
"no charger included," "New Old Stock," "antique," "replica." It flows through the
existing pipeline and steers three things: AI extraction, pricing (especially when no
sold-comp history exists), and the generated description.

This is a single-user self-tool. The seller is honest and experienced; if a fact is in
the note it is because it matters and is not visible in the photo, or the seller wants it
reflected. The note therefore **complements** the images and is not adversarially
reconciled against them.

## Decisions (locked during brainstorming)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Entry point | WhatsApp caption only | Matches the "send pics + note" flow; main capture path |
| Price impact model | AI infers (no structured rules) | Everything-seller; notes vary too widely to enumerate rules |
| Trust model | Trusted, additive, complements photos | Honest single user; note fills the non-visible |
| Description disclosure | AI weaves it in | Note already in vision prompt → `description_html` reflects it; no template change |
| Frontend | Skipped for now | Entry is WhatsApp-only; UI display deferred |
| Note format | Free text only | No structured price-hint parsing in v1 |

## Trust framing (exact intent)

The note is injected into AI prompts as **SELLER-PROVIDED CONTEXT**: trusted, supplied
because it matters and is not visible in the photos. The AI must *use* it. It complements
the images; it does not contradict clearly visible evidence. No conflict-flagging, no
reconciliation gate, no review interruption.

## Data flow

```
WhatsApp caption ("...no charger... sell")
  └─> Hermes plugin (pre_gateway_dispatch): strip "sell" trigger, keep remainder as note
       └─> capture_to_dc.py  --note "<text>"
            └─> POST /api/capture { path, note }
                 └─> queue_manager.add_folder(metadata={..., note})  →  job.note  (DB column)
                      ├─> AI vision  (ai_analyzer.analyze_item)        — fills non-visible facts
                      ├─> Pricing    (pricing_engine grounding)        — steers comps + no-history fallback
                      └─> Description (AI description_html)             — honest disclosure, emergent
```

## Components

Six backend touch points. Each is implemented test-first (see Testing).

### 1. Hermes plugin — `integrations/hermes/plugin/__init__.py`
- The inbound caption arrives as `event.text`. The message carrying "sell" is the one with
  the caption (WhatsApp delivers album frames as separate messages; only one has text —
  existing behavior).
- Derive the note: take `event.text`, remove the "sell" trigger as a **whole word,
  case-insensitive**, collapse resulting whitespace, trim. The remainder is the note (may be
  empty). Residual filler (e.g. `"I want to  this antique"` from `"I want to sell this
  antique"`) is harmless — it is context for the AI, not displayed verbatim. Exactness is not
  required.
- Pass it to the bridge as a new `--note "<text>"` argument on the existing `subprocess.Popen`
  calls (both the `--collect` path and the direct-media fallback path).
- If note derivation fails, omit `--note` — capture proceeds unchanged.

### 2. Capture bridge — `integrations/hermes/capture_to_dc.py`
- Add `--note` to the `argparse` parser.
- Include it in the existing `POST /api/capture` body: `{'path': folder, 'note': note}`.

### 3. Capture endpoint — `backend/app/blueprints/api/queue_api.py` (`capture_item`, ~line 156)
- Read `note` from `request.json`.
- Sanitize and length-cap (reuse project sanitizer; cap e.g. 500 chars).
- Pass into the existing `add_folder(metadata={'capture_source': 'hermes', 'note': note})`.
- Missing/empty note → behave exactly as today.

### 4. Persistence — `backend/app/services/queue_manager.py` (`add_folder`, ~line 228)
- The `job.note` column already exists (`backend/app/core/database.py:54`) but is currently
  never written.
- In the `if metadata:` block, map `metadata['note'] → job.note`, mirroring the existing
  `condition` mapping. This persists the note atomically with job creation (survives restart).

### 5. AI vision — `backend/app/core/prompts.py` + `backend/app/services/ai_analyzer.py`
- Add a `{seller_note}` placeholder block to `EBAY_LISTING_PROMPT` with the trust framing
  above. When empty, the block collapses to nothing.
- `analyze_item(self, image_paths, category_suggestions="")` gains a `seller_note=""`
  parameter; `EBAY_LISTING_PROMPT.format(...)` (~line 136) passes it through.
- `analyze_with_research(...)` (~line 570) threads the note down to `analyze_item` and into
  the research query (`INDUSTRIAL_RESEARCH_PROMPT`, ~line 519) so condition/provenance
  cues (NOS, antique, replica) shape comp selection.
- The orchestrator that calls the analyzer (processor/listing agent) reads `job.note` and
  passes it in.

### 6. Pricing — `backend/app/services/pricing_engine.py`
- Thread the note into `get_price_with_comps(...)` (~line 525) and down into
  `get_ai_price_estimate(...)` (~line 344) — the Gemini grounding / estimate fallback at the
  **bottom** of the pricing cascade.
- This is the "no eBay history" payoff: when ISBN/MPN/keyword/comp lookups return nothing,
  the note plus web grounding drive a *reasoned* price instead of a blind default.
- The note's influence is recorded in the existing pricing reasoning string already
  persisted to job metadata, so the seller can see *why* it priced that way.

### Description (emergent, no separate component)
Because the note is in the vision prompt, the AI-generated `description_html` naturally folds
in disclosures ("Charger not included," "New Old Stock"). No template change in
`processor_service`. All AI/description output remains HTML-escaped as today.

## Safety properties

- **Empty-note path is byte-identical to today.** No note → `{seller_note}` collapses to
  empty → prompts and pricing inputs are unchanged. Pinned by a regression test. This is the
  core no-regression guarantee.
- **Note is best-effort.** Any failure in derivation/threading → the job proceeds without the
  note. A note never blocks or fails a listing.
- **Injection-safe.** The note is user free text that reaches an LLM prompt and the HTML
  description. It is length-capped, sanitized at the endpoint, and HTML-escaped on the
  description path (consistent with existing research-data handling).

## Testing (TDD — failing test first for each)

1. **Plugin strip:** caption `"blue widget no charger sell"` → note `"blue widget no charger"`
   (trigger removed, trimmed).
2. **Bridge → endpoint:** `POST /api/capture` with `note` → `job.note` persisted.
3. **add_folder mapping:** `metadata={'note': ...}` → `job.note` column set.
4. **Vision prompt present:** note non-empty → rendered prompt contains the note block.
5. **Vision prompt absent (regression):** note empty/None → rendered prompt is identical to
   the current prompt (no stray block, no whitespace drift).
6. **Pricing threading:** note flows into `get_ai_price_estimate` (grounding) call.
7. **Description escaping:** a note with HTML/script characters is escaped in output.

Run `pytest tests/unit -v` after each item. Suite is green at 409+ today; new tests add to it.

## Out of scope (v1)

- Frontend display/edit of the note.
- Structured note parsing (price floors, command syntax).
- Folder-scan and web-upload entry points (WhatsApp caption only for now).
- Any structured-rule pricing multipliers.

## Deploy & activation

Work lands on `feature/seller-notes` with per-task commits. The assistant carries it all the
way to live — merge and restart are part of delivery, not a manual chore handed back.

1. **Build test-first**, per-task commits on `feature/seller-notes`.
2. **Merge on green:** once the full unit suite (409+) passes, merge `feature/seller-notes`
   into `master` and push.
3. **Activate (assistant performs):**
   - **DC backend** — no hot-reload by design; restart it (via `/api/system/restart` or the
     service restart) so the new Python loads.
   - **Hermes gateway** — plugin code only takes effect after a gateway restart; the assistant
     triggers it.

### Why explicit restart, not a live auto-reload watcher
A file-watch reloader is **deliberately rejected**. The DC service is Flask-SocketIO under
detached `pythonw`; the Werkzeug reloader double-spawns worker processes there — the exact
"Continuous wsgi_service Process Spawning" failure observed 2026-06-22. An explicit restart is
deterministic and side-effect-free. Hermes plugin code cannot hot-reload regardless, so a
gateway restart is inherent. Revisit only if a clean, SocketIO-safe reload mechanism is later
desired.
