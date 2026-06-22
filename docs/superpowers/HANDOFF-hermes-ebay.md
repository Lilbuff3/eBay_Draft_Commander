# Hermes → eBay capture — STATE & HANDOFF (resume here next session)

## TL;DR
WhatsApp photo + caption "sell" → Hermes plugin → Draft Commander → **real eBay scheduled listing**.
It **works end-to-end** — a live scheduled listing was created (job `53a17206`). Branch
`feature/hermes-capture`, **21 commits**, **1 unpushed** (`dfa4c23` — PUSH IT to back up).

## How to resume (fast)
1. `cd C:\Users\adam\Projects\ebay-draft-commander` ; `git checkout feature/hermes-capture` ; `git pull`.
2. Start DC (it does NOT persist across sessions): `python backend/wsgi.py` (port 5000). Wait for `/api/system/health` ok.
3. Hermes gateway persists (Windows scheduled task `Hermes_Gateway`) + the plugin is installed & enabled.
4. In WhatsApp **"Message yourself"**, send an item photo with caption **`sell`** → expect a `Scheduled: …` reply.

## Durable locations
- Git: branch `feature/hermes-capture` (origin `Lilbuff3/eBay_Draft_Commander`). ⚠ `dfa4c23` is local-only — push it.
- Hermes plugin (installed+enabled): `C:\Users\adam\AppData\Local\hermes\plugins\ebay-capture\` (`plugin.yaml`+`__init__.py`). Repo copy: `integrations/hermes/plugin/`.
- Hermes config: `~/.hermes/.env` (`DC_REPO`, `DC_API_BASE`, `DC_CAPTURES_DIR`, `WHATSAPP_ALLOWED_USERS` incl. LID `191513027965178`, `GEMINI_API_KEY`); `config.yaml` model = `gemini-2.5-flash` via `gemini` provider (free).
- Bridge: `integrations/hermes/capture_to_dc.py` (`--chat-id`/`--bridge-port`/`--cancel`, `/send` reply, `.last_job`).

## What's DONE & working
- **Deterministic trigger** (the big win): Hermes plugin `pre_gateway_dispatch` hook (`gateway/run.py:7230`) fires BEFORE the LLM. photo+"sell" → launch bridge (detached) → `{action:skip}` (LLM bypassed). Proven: gateway log `pre_gateway_dispatch skip: reason=ebay capture launched`. cancel-last + normal-chat passthrough verified offline.
- Full pipeline reaches eBay: capture endpoint → AI (Gemini vision) → category → pricing → image upload → Trading API `AddFixedPriceItem` → **scheduled listing created**.
- Four production bugs found via real runs + fixed (all committed):
  - `31fd6f3` image-upload allowlist missing `captures/`.
  - `2936497` price floor (eBay error 73 when price was ~$0).
  - `eacfebe` TOCTOU slot race (single-insert scheduled_time).
  - `40228cc` + `dfa4c23` smart pricing (below).
- Tests: 9 bridge/pricing unit tests green; offline e2e proves slot→Trading wiring.

## Smart pricing (the current focus — almost there)
- **Validated standalone:** Gemini grounding fed part#/MPN/brand reasons real prices — the hard video card → **$380** ("industrial FPGA broadcast hw, MSRP ~$950, 40% used → $380"), not the $30 default.
- **In-pipeline bug found & FIXED (`dfa4c23`):** a `None`-valued identifier field made `_build_keyword_query` call `None.strip()` → crashed the whole pricing cascade BEFORE Gemini ran → defaulted to $24.99. Guarded with `(… or '')`. Regression test `tests/unit/test_pricing_query.py`.
- **NEEDS CONFIRMING:** the last live listing (`53a17206`) was created at the $24.99 default (it hit the None bug). After `dfa4c23` + DC restart, the NEXT `sell` capture should price via Gemini (~real value). **First task next session: send one sell photo, confirm the price is reasoned (not $24.99), check eBay Seller Hub → Scheduled.**

## Remaining work / improvements
1. Confirm smart pricing in a live run (above).
2. **Browser-evaluate a real listing** (user offered eBay browser access via claude-in-chrome MCP): check title quality (80-char SEO), photos/cover, category, item specifics, description render → concrete fixes.
3. Pricing polish: stop relying on the 403 HTML scraper (`ebay/researcher.py`) — it's noise now that Gemini is the fallback; optionally widen Browse API queries; clear the eBay warning 21927 (`ShippingPackageDetails.MeasurementSystem` undeclared element).
4. `integrations/hermes/README.md` — document the PLUGIN as the trigger (SKILL.md is legacy).
5. **Persistent DC** — runs only inside the assistant session now; add a scheduled task / keep a terminal open for daily use.
6. DST pytz bug (chip `task_67c907f8`) in `get_next_optimal_listing_time`.
7. Finish the branch — PR (like #67) or merge to master.

## Key source refs
- Plugin: `gateway/run.py:7230-7262`; `hermes_cli/plugins.py:155/997/1683` (hook/register/invoke, sync).
- Pricing: `pricing_engine.py` get_price_with_comps / `get_ai_price_estimate` (identifiers + never-0) / `_build_keyword_query` (None guard) / strategy-3 grounding (`:637`); floor in `processor_service.py` after `get_final_pricing`; `image_processor.py:66-90` allowlist.
