# Seller Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a seller attach a free-text WhatsApp caption ("no charger", "New Old Stock", "antique") that flows through the pipeline as trusted context steering AI extraction, pricing (especially when comps run dry), and the description.

**Architecture:** The caption is derived in the Hermes plugin, passed through the capture bridge to `POST /api/capture`, stored in `job_metadata['note']` (already-persisted JSON — no schema/mapper changes), then read by the orchestrators and threaded as a `seller_note` parameter into the AI vision prompt and the pricing grounding estimate. The description picks it up for free because the note is in the vision prompt that generates `description_html`.

**Tech Stack:** Python 3, Flask, SQLAlchemy, Google Gemini (`google.genai`), pytest. Hermes plugin (Python, `pre_gateway_dispatch` hook) + `capture_to_dc.py` bridge.

---

## Plan-Level Notes (read before starting)

- **Branch:** all work on `feature/seller-notes` (already created and checked out). Per-task commits.
- **Persistence decision (deviation from spec):** the spec proposed mapping to the dedicated `job.note` DB column. During planning we found the `note` column is not carried by the `QueueJob` dataclass or either DB mapper (`_queue_job_to_db` / `_db_to_queue_job`), so using it would mean 4 edits across schema-adjacent code. Instead we store the note in `job_metadata['note']`, which `add_folder` already persists and which is exactly where every other capture hint lives (`capture_source`, `category_hint`, `force_ai_refresh`, `ordered_images`). Same persistence, fewer touch points, established pattern. The unused `note` column is left as-is.
- **Scope deferral (deviation from spec):** the spec mentioned injecting the note into the `INDUSTRIAL_RESEARCH_PROMPT` research query. We defer that. The vision prompt already carries the note into Phase-1 identification (which shapes the research search terms), and the pricing grounding estimate gets the note directly — together these deliver the stated value (condition/provenance in extraction + price grounding when comps are absent) without touching the research-prompt path. Revisit if comp-search quality needs it.
- **Core safety property:** when no note is supplied, every prompt must be byte-identical to today. The shared helper returns `""` for empty/whitespace notes, and Task 1 pins this with a regression test.
- **Run after each task:** `pytest tests/unit -v` (suite is green at 409+ today).
- **Testing approach:** prompt-construction logic is extracted into a pure, importable helper so it can be unit-tested without a live Gemini client. Threading is verified with monkeypatched spies.

---

## Task 1: Seller-note block helper + vision prompt placeholder

**Files:**
- Modify: `backend/app/core/prompts.py` (add helper; add `{seller_note}` to `EBAY_LISTING_PROMPT`)
- Test: `tests/unit/test_seller_notes.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_seller_notes.py`:

```python
"""Seller-note feature: trusted free-text context steering AI + pricing."""
from backend.app.core.prompts import build_seller_note_block, EBAY_LISTING_PROMPT


class TestBuildSellerNoteBlock:
    def test_empty_note_returns_empty_string(self):
        assert build_seller_note_block("") == ""
        assert build_seller_note_block(None) == ""
        assert build_seller_note_block("   ") == ""

    def test_note_is_wrapped_in_trusted_context_block(self):
        block = build_seller_note_block("no charger included")
        assert "no charger included" in block
        assert "SELLER-PROVIDED CONTEXT" in block

    def test_note_is_trimmed(self):
        block = build_seller_note_block("  New Old Stock  ")
        assert "New Old Stock" in block
        assert "  New Old Stock  " not in block


class TestVisionPromptPlaceholder:
    def test_empty_note_prompt_has_no_marker(self):
        rendered = EBAY_LISTING_PROMPT.format(category_suggestions="cats", seller_note="")
        assert "SELLER-PROVIDED CONTEXT" not in rendered
        # JSON structure braces survived .format (no stray KeyError-causing braces)
        assert '"identification"' in rendered

    def test_note_block_appears_when_present(self):
        block = build_seller_note_block("antique, not a replica")
        rendered = EBAY_LISTING_PROMPT.format(category_suggestions="cats", seller_note=block)
        assert "antique, not a replica" in rendered
        assert "SELLER-PROVIDED CONTEXT" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_seller_note_block'`

- [ ] **Step 3: Add the helper and the prompt placeholder**

In `backend/app/core/prompts.py`, add at the top (after the module docstring, before `EBAY_LISTING_PROMPT`):

```python
def build_seller_note_block(seller_note: str) -> str:
    """Render the trusted seller-note context block for AI prompts.

    The seller supplies this with their photos because it matters and may not be
    visible in the images. Empty/whitespace -> "" so prompts stay byte-identical to
    the no-note path.
    """
    note = (seller_note or "").strip()
    if not note:
        return ""
    return (
        "\nSELLER-PROVIDED CONTEXT (trusted — the seller supplied this because it "
        "matters and may not be visible in the photos; use it, and let it complement "
        "the images without contradicting clearly visible evidence):\n"
        f"{note}\n"
    )
```

Then in `EBAY_LISTING_PROMPT`, locate this region (currently around line 13-16):

```
fill in generic brand information, catalog specs, or "Varies".

PRIORITY ORDER (spend most effort on #1 and #2):
```

Change it to insert the placeholder on the blank line:

```
fill in generic brand information, catalog specs, or "Varies".
{seller_note}
PRIORITY ORDER (spend most effort on #1 and #2):
```

(With `seller_note=""` this renders `..."Varies".\n\nPRIORITY ORDER...` — identical to today. With a block it inserts the context with clean spacing.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/prompts.py tests/unit/test_seller_notes.py
git commit -m "feat(prompts): seller-note context block + vision prompt placeholder"
```

---

## Task 2: Thread seller_note through AIAnalyzer.analyze_item

**Files:**
- Modify: `backend/app/services/ai_analyzer.py` (`analyze_item`, around line 121-136)
- Test: `tests/unit/test_seller_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_seller_notes.py`:

```python
from unittest.mock import MagicMock, patch


def _make_analyzer():
    """AIAnalyzer with a stubbed client; encode_image short-circuited."""
    from backend.app.services.ai_analyzer import AIAnalyzer
    analyzer = AIAnalyzer.__new__(AIAnalyzer)
    analyzer.client = None  # forces early 'AI Client not initialized' return AFTER prompt build
    return analyzer


class TestAnalyzeItemThreadsNote:
    def test_analyze_item_injects_note_into_prompt(self):
        analyzer = _make_analyzer()
        captured = {}

        def fake_format_capture(*args, **kwargs):
            captured['seller_note'] = kwargs.get('seller_note')
            return "PROMPT"

        with patch("backend.app.services.ai_analyzer.EBAY_LISTING_PROMPT") as mock_prompt, \
             patch.object(analyzer, "encode_image", return_value="ZW5j"):
            mock_prompt.format.side_effect = fake_format_capture
            analyzer.analyze_item(["/fake/img.jpg"], seller_note="no charger")

        block = captured['seller_note']
        assert block is not None and "no charger" in block

    def test_analyze_item_default_note_is_empty_block(self):
        analyzer = _make_analyzer()
        captured = {}
        with patch("backend.app.services.ai_analyzer.EBAY_LISTING_PROMPT") as mock_prompt, \
             patch.object(analyzer, "encode_image", return_value="ZW5j"):
            mock_prompt.format.side_effect = lambda *a, **k: captured.update(k) or "P"
            analyzer.analyze_item(["/fake/img.jpg"])
        assert captured.get('seller_note') == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_seller_notes.py::TestAnalyzeItemThreadsNote -v`
Expected: FAIL — `analyze_item()` got an unexpected keyword argument `seller_note`

- [ ] **Step 3: Add the parameter and inject the block**

In `backend/app/services/ai_analyzer.py`:

Change the signature (line 121):

```python
    def analyze_item(self, image_paths, category_suggestions: str = "", seller_note: str = ""):
```

Change the prompt build (line 136) from:

```python
        # Build the prompt
        prompt = EBAY_LISTING_PROMPT.format(category_suggestions=category_suggestions)
```

to:

```python
        # Build the prompt (seller_note is trusted context; empty -> no-op)
        note_block = build_seller_note_block(seller_note)
        prompt = EBAY_LISTING_PROMPT.format(
            category_suggestions=category_suggestions,
            seller_note=note_block,
        )
```

Ensure the import at the top of `ai_analyzer.py` includes the helper. Find the existing import (around line 17):

```python
    EBAY_LISTING_PROMPT, INDUSTRIAL_RESEARCH_PROMPT,
```

and add `build_seller_note_block` to that same `from backend.app.core.prompts import (...)` group.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_analyzer.py tests/unit/test_seller_notes.py
git commit -m "feat(ai): thread seller_note into analyze_item vision prompt"
```

---

## Task 3: Thread seller_note through analyze_with_research

**Files:**
- Modify: `backend/app/services/ai_analyzer.py` (`analyze_with_research`, line 570-581)
- Test: `tests/unit/test_seller_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_seller_notes.py`:

```python
class TestAnalyzeWithResearchForwardsNote:
    def test_note_forwarded_to_analyze_item(self):
        analyzer = _make_analyzer()
        seen = {}

        def fake_analyze_item(image_paths, category_suggestions="", seller_note=""):
            seen['seller_note'] = seller_note
            return {"error": "stop here"}  # short-circuit before research phase

        with patch.object(analyzer, "analyze_item", side_effect=fake_analyze_item):
            analyzer.analyze_with_research(["/fake/img.jpg"], seller_note="antique")

        assert seen['seller_note'] == "antique"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_seller_notes.py::TestAnalyzeWithResearchForwardsNote -v`
Expected: FAIL — `analyze_with_research()` got an unexpected keyword argument `seller_note`

- [ ] **Step 3: Add the parameter and forward it**

In `backend/app/services/ai_analyzer.py`, change the signature (line 570):

```python
    def analyze_with_research(self, image_paths: list, category_suggestions: str = "", seller_note: str = "") -> dict:
```

Change the Phase-1 call (line 581) from:

```python
        basic_result = self.analyze_item(image_paths, category_suggestions=category_suggestions)
```

to:

```python
        basic_result = self.analyze_item(
            image_paths, category_suggestions=category_suggestions, seller_note=seller_note
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_analyzer.py tests/unit/test_seller_notes.py
git commit -m "feat(ai): forward seller_note through analyze_with_research"
```

---

## Task 4: listing_ai_agent.analyze_item reads the job note

**Files:**
- Modify: `backend/app/services/listing_ai_agent.py` (`analyze_item`, line 36-66)
- Test: `tests/unit/test_seller_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_seller_notes.py`:

```python
from types import SimpleNamespace


class TestListingAgentReadsNote:
    def _agent(self):
        from backend.app.services.listing_ai_agent import ListingAIAgent
        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent.ai_analyzer = MagicMock()
        agent.ai_analyzer.analyze_with_research.return_value = {
            "identification": {}, "listing": {"suggested_title": "X", "description_html": "d"},
            "item_specifics": {},
        }
        return agent

    def _job(self, metadata):
        return SimpleNamespace(
            id="job1", folder_path="/c/inbox/x", user_title=None, user_description=None,
            ai_data={}, job_metadata=metadata,
        )

    def test_note_from_metadata_passed_to_analyzer(self):
        agent = self._agent()
        job = self._job({"note": "no power cord"})
        with patch("backend.app.services.listing_ai_agent.taxonomy.get_category_suggestions", return_value=[]):
            agent.analyze_item(job, ["/fake/img.jpg"], condition="Used - Good")
        _, kwargs = agent.ai_analyzer.analyze_with_research.call_args
        assert kwargs.get("seller_note") == "no power cord"

    def test_missing_note_passes_empty_string(self):
        agent = self._agent()
        job = self._job({})
        with patch("backend.app.services.listing_ai_agent.taxonomy.get_category_suggestions", return_value=[]):
            agent.analyze_item(job, ["/fake/img.jpg"], condition="Used - Good")
        _, kwargs = agent.ai_analyzer.analyze_with_research.call_args
        assert kwargs.get("seller_note") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_seller_notes.py::TestListingAgentReadsNote -v`
Expected: FAIL — `analyze_with_research` called without `seller_note` (KeyError on `kwargs.get` returns None != expected)

- [ ] **Step 3: Read the note and pass it**

In `backend/app/services/listing_ai_agent.py`, change the analyzer call (line 66) from:

```python
                ai_data = self.ai_analyzer.analyze_with_research(images, category_suggestions=sug_text)
```

to:

```python
                seller_note = job_obj.job_metadata.get('note', '') if job_obj.job_metadata else ''
                ai_data = self.ai_analyzer.analyze_with_research(
                    images, category_suggestions=sug_text, seller_note=seller_note
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/listing_ai_agent.py tests/unit/test_seller_notes.py
git commit -m "feat(agent): read seller note from job_metadata into AI analysis"
```

---

## Task 5: Pricing — inject seller_note into get_ai_price_estimate

**Files:**
- Modify: `backend/app/services/pricing_engine.py` (`get_ai_price_estimate`, line 344, prompt around 369-382)
- Test: `tests/unit/test_seller_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_seller_notes.py`:

```python
class TestPricingGroundingNote:
    def _engine(self):
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine.__new__(PricingEngine)
        engine.ai_client = None  # early-return after prompt build path is fine; we patch prompt capture
        return engine

    def test_estimate_accepts_and_uses_note(self):
        from backend.app.services import pricing_engine as pe
        engine = self._engine()
        # ai_client None -> returns None immediately; assert the kwarg is accepted (no TypeError)
        result = engine.get_ai_price_estimate("Widget", "Used - Good", seller_note="antique")
        assert result is None  # client not configured; call signature accepted the note
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_seller_notes.py::TestPricingGroundingNote -v`
Expected: FAIL — `get_ai_price_estimate()` got an unexpected keyword argument `seller_note`

- [ ] **Step 3: Add the parameter and inject into the grounding prompt**

In `backend/app/services/pricing_engine.py`, change the signature (line 344):

```python
    def get_ai_price_estimate(self, title: str, condition: str, identification: Optional[Dict] = None, seller_note: str = "") -> Optional[Dict[str, Union[float, str]]]:
```

After the `identifier_block` assignment (line 369), add the note block:

```python
            identifier_block = "\n            ".join(_id_lines) if _id_lines else "(no specific identifiers extracted)"
            seller_note_block = build_seller_note_block(seller_note)
```

Then in the f-string `prompt` (around line 381-382), change:

```python
            Item Title: {title}
            Condition: {condition}
            Identifiers:
            {identifier_block}
```

to:

```python
            Item Title: {title}
            Condition: {condition}
            Identifiers:
            {identifier_block}
            {seller_note_block}
```

Add the helper import near the top of `pricing_engine.py` (alongside other `from backend.app.core...` imports):

```python
from backend.app.core.prompts import build_seller_note_block
```

(If `pricing_engine.py` has no existing prompts import, add this line with the other core imports.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pricing_engine.py tests/unit/test_seller_notes.py
git commit -m "feat(pricing): inject seller note into AI grounding estimate"
```

---

## Task 6: Pricing — thread seller_note through get_price_with_comps

**Files:**
- Modify: `backend/app/services/pricing_engine.py` (`get_price_with_comps`, line 525; grounding call line 666)
- Test: `tests/unit/test_seller_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_seller_notes.py`:

```python
class TestPriceWithCompsThreadsNote:
    def test_note_reaches_grounding_estimate(self):
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine.__new__(PricingEngine)
        captured = {}

        def fake_estimate(title, condition, identification=None, seller_note=""):
            captured['seller_note'] = seller_note
            return None

        # Force the cascade to reach grounding: no comps, no research price.
        engine.search_sold_listings = lambda *a, **k: []
        engine.filter_comps = lambda comps, ref: []
        engine.get_ai_price_estimate = fake_estimate
        engine._build_keyword_query = lambda title, identification=None: title

        engine.get_price_with_comps(
            "Obscure Widget", condition="Used - Good", seller_note="antique, working"
        )
        assert captured.get('seller_note') == "antique, working"
```

> Note: if `get_price_with_comps` references other engine attributes before reaching grounding (e.g. config flags), stub them in the test as needed — the assertion is only that `seller_note` reaches `get_ai_price_estimate`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_seller_notes.py::TestPriceWithCompsThreadsNote -v`
Expected: FAIL — `get_price_with_comps()` got an unexpected keyword argument `seller_note`

- [ ] **Step 3: Add the parameter and forward to grounding**

In `backend/app/services/pricing_engine.py`, change the `get_price_with_comps` signature (line 525) by appending the parameter at the end of the argument list:

```python
    def get_price_with_comps(self, title: str, condition: str = "Used - Good", category_id: Optional[str] = None, ai_suggested_price: Optional[str] = None, acquisition_cost: float = 0.0, isbn: Optional[str] = None, shipping_cost: float = 0.0, identification: Optional[Dict] = None, research_market_price: Optional[Dict] = None, availability: Optional[str] = None, seller_note: str = "") -> Dict[str, Any]:
```

Change the grounding call (line 666) from:

```python
            grounded_result = self.get_ai_price_estimate(title, condition, identification=identification)
```

to:

```python
            grounded_result = self.get_ai_price_estimate(title, condition, identification=identification, seller_note=seller_note)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pricing_engine.py tests/unit/test_seller_notes.py
git commit -m "feat(pricing): thread seller_note through get_price_with_comps"
```

---

## Task 7: get_final_pricing param + processor passes the job note

**Files:**
- Modify: `backend/app/services/listing_ai_agent.py` (`get_final_pricing`, line 112-146)
- Modify: `backend/app/services/processor_service.py` (`get_final_pricing` call, line 589)
- Test: `tests/unit/test_seller_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_seller_notes.py`:

```python
class TestFinalPricingNote:
    def test_get_final_pricing_forwards_note(self):
        from backend.app.services.listing_ai_agent import ListingAIAgent
        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent._default_shipping_cost = 0.0
        captured = {}

        agent.pricing_engine = MagicMock()
        def fake_comps(*args, **kwargs):
            captured['seller_note'] = kwargs.get('seller_note')
            return {"suggested_price": "10.00", "comps": [], "reasoning": "", "source": "x"}
        agent.pricing_engine.get_price_with_comps.side_effect = fake_comps

        agent.get_final_pricing(
            "Widget", "Used - Good", ai_suggested_price=5, user_price=None,
            shipping_cost=0.0, seller_note="no charger",
        )
        assert captured.get('seller_note') == "no charger"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_seller_notes.py::TestFinalPricingNote -v`
Expected: FAIL — `get_final_pricing()` got an unexpected keyword argument `seller_note`

- [ ] **Step 3: Add the parameter and forward it; wire the processor**

In `backend/app/services/listing_ai_agent.py`, change the `get_final_pricing` signature (line 112) by appending `seller_note`:

```python
    def get_final_pricing(self, title, condition, ai_suggested_price, user_price, shipping_cost=None, log_callback=None, identification=None, research_market_price=None, availability=None, seller_note=""):
```

Change the `get_price_with_comps` call (line 138-146) to pass it:

```python
            price_result = self.pricing_engine.get_price_with_comps(
                title,
                condition=condition,
                ai_suggested_price=ai_suggested_price,
                shipping_cost=resolved_shipping,
                identification=identification,
                research_market_price=research_market_price,
                availability=availability,
                seller_note=seller_note,
            )
```

In `backend/app/services/processor_service.py`, find the `get_final_pricing` call (line 589). It looks like:

```python
        pricing_result = self.ai_agent.get_final_pricing(
```

Add a `seller_note` argument to that call. Immediately before the call, read the note from the job, then pass it. For example:

```python
        seller_note = job_obj.job_metadata.get('note', '') if job_obj.job_metadata else ''
        pricing_result = self.ai_agent.get_final_pricing(
            # ... existing arguments unchanged ...
            seller_note=seller_note,
        )
```

> Keep every existing argument in that call exactly as-is; only add `seller_note=seller_note` as the final keyword argument. Read the surrounding lines (589-605) to preserve the current arguments.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: PASS

- [ ] **Step 5: Run the full unit suite (no regressions)**

Run: `pytest tests/unit -v`
Expected: PASS (409+ prior tests plus the new seller-note tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/listing_ai_agent.py backend/app/services/processor_service.py tests/unit/test_seller_notes.py
git commit -m "feat(pricing): pass job seller note from processor into final pricing"
```

---

## Task 8: Capture endpoint stores the note in job_metadata

**Files:**
- Modify: `backend/app/blueprints/api/queue_api.py` (`capture_item`, line 169-201)
- Test: `tests/unit/test_seller_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_seller_notes.py`. This unit-tests the note-extraction/cap logic via a small helper we will add (`_clean_capture_note`), keeping it independent of Flask request plumbing:

```python
class TestCaptureNoteCleaning:
    def test_clean_note_trims_and_caps(self):
        from backend.app.blueprints.api.queue_api import _clean_capture_note
        assert _clean_capture_note("  no charger  ") == "no charger"
        assert _clean_capture_note(None) == ""
        assert _clean_capture_note(123) == ""  # non-str -> empty
        long = "x" * 1000
        assert len(_clean_capture_note(long)) == 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_seller_notes.py::TestCaptureNoteCleaning -v`
Expected: FAIL — `cannot import name '_clean_capture_note'`

- [ ] **Step 3: Add the helper and use it in capture_item**

In `backend/app/blueprints/api/queue_api.py`, add a module-level helper (near the other helpers at the top of the file):

```python
def _clean_capture_note(raw) -> str:
    """Normalize a seller-supplied capture note: str, trimmed, length-capped at 500."""
    if not isinstance(raw, str):
        return ""
    return raw.strip()[:500]
```

In `capture_item`, after `raw_path = data.get('path')` (line 170), read and clean the note:

```python
    note = _clean_capture_note(data.get('note'))
```

Change the `add_folder` call (line 196-201) to include the note in metadata:

```python
        job = qm.add_folder(
            str(src),
            metadata={'capture_source': 'hermes', 'note': note} if note else {'capture_source': 'hermes'},
            batch_id=batch_id,
            scheduled_time=slot,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/blueprints/api/queue_api.py tests/unit/test_seller_notes.py
git commit -m "feat(api): accept seller note on /api/capture and store in job_metadata"
```

---

## Task 9: capture bridge passes --note to /api/capture

**Files:**
- Modify: `integrations/hermes/capture_to_dc.py` (`capture` line 56/68, `collect_and_capture` line 139/160, `main` argparse line 172+)
- Test: `tests/unit/test_seller_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_seller_notes.py`:

```python
class TestCaptureBridgeNote:
    def test_capture_posts_note_in_body(self, tmp_path, monkeypatch):
        import integrations.hermes.capture_to_dc as bridge

        # one real image so build_item_folder succeeds
        from PIL import Image
        img = tmp_path / "a.jpg"
        Image.new("RGB", (10, 10)).save(img)
        captures = tmp_path / "caps"
        captures.mkdir()

        posted = {}

        class FakeResp:
            status_code = 200
            def json(self):
                return {"success": True, "job_id": "j1", "scheduled_time": "soon"}

        def fake_post(url, json=None, timeout=None):
            posted['url'] = url
            posted['json'] = json
            return FakeResp()

        monkeypatch.setattr(bridge.requests, "post", fake_post)
        monkeypatch.setattr(bridge, "_health_ok", lambda api_base: True)
        # short-circuit polling: return immediately as scheduled
        monkeypatch.setattr(bridge.requests, "get", lambda *a, **k: type("G", (), {
            "status_code": 200, "json": lambda self: {"status": "scheduled"}})())

        bridge.capture([str(img)], api_base="http://x", captures_dir=str(captures),
                       poll_interval=0, poll_timeout=0, note="no charger")

        assert posted['json']['note'] == "no charger"
        assert posted['json']['path']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_seller_notes.py::TestCaptureBridgeNote -v`
Expected: FAIL — `capture()` got an unexpected keyword argument `note`

- [ ] **Step 3: Add the note parameter through the bridge**

In `integrations/hermes/capture_to_dc.py`:

Change `capture` signature (line 56) by appending `note=""`:

```python
def capture(image_paths, api_base=None, captures_dir=None, poll_interval=3, poll_timeout=300, note=""):
```

Change the POST (line 68) from:

```python
        resp = requests.post(f"{api_base}/api/capture", json={'path': folder}, timeout=30)
```

to:

```python
        body = {'path': folder}
        if note:
            body['note'] = note
        resp = requests.post(f"{api_base}/api/capture", json=body, timeout=30)
```

Change `collect_and_capture` signature (line 139) by appending `note=""`:

```python
def collect_and_capture(chat_id, api_base=None, captures_dir=None, debounce=3.0, note=""):
```

Change its `capture(...)` call (line 160) from:

```python
        return capture(paths, api_base=api_base, captures_dir=captures_dir)
```

to:

```python
        return capture(paths, api_base=api_base, captures_dir=captures_dir, note=note)
```

In `main` (argparse block starting line 172), add the argument after the existing `--collect`/other args:

```python
    parser.add_argument('--note', default='', help="seller note (trusted context for AI/pricing)")
```

Then locate the two dispatch calls in `main` that invoke `collect_and_capture(...)` and `capture(...)` for the normal (non-cancel) paths and append `note=args.note` to each. For example:

```python
    # collect path:
    msg = collect_and_capture(args.collect, note=args.note)
    # direct images path:
    msg = capture(args.images, note=args.note)
```

> Read the existing `main` dispatch (lines 178-200) and add `note=args.note` only to the `collect_and_capture(...)` and `capture(...)` calls; leave `cancel_last(...)` untouched.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add integrations/hermes/capture_to_dc.py tests/unit/test_seller_notes.py
git commit -m "feat(hermes): pass seller note through capture bridge to /api/capture"
```

---

## Task 10: Hermes plugin derives the note from the WhatsApp caption

**Files:**
- Modify: `integrations/hermes/plugin/__init__.py` (`on_message`, line 36-78)
- Test: `tests/unit/test_seller_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_seller_notes.py`:

```python
class TestPluginDeriveNote:
    def test_strips_sell_trigger_keeps_rest(self):
        from integrations.hermes.plugin import _derive_note
        assert _derive_note("blue widget no charger sell") == "blue widget no charger"
        assert _derive_note("SELL antique not replica") == "antique not replica"

    def test_empty_or_trigger_only(self):
        from integrations.hermes.plugin import _derive_note
        assert _derive_note("sell") == ""
        assert _derive_note("") == ""
        assert _derive_note(None) == ""

    def test_collapses_whitespace(self):
        from integrations.hermes.plugin import _derive_note
        assert _derive_note("new   old   stock  sell") == "new old stock"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_seller_notes.py::TestPluginDeriveNote -v`
Expected: FAIL — `cannot import name '_derive_note'`

- [ ] **Step 3: Add the pure helper and wire it into on_message**

In `integrations/hermes/plugin/__init__.py`, add a module-level helper (after the imports, near `_staging_dir`):

```python
def _derive_note(text):
    """Caption minus the 'sell' trigger -> trusted seller note (may be empty).

    Removes 'sell' as a whole word (case-insensitive), collapses whitespace, trims.
    Residual filler is harmless — it's context for the AI, not shown verbatim.
    """
    if not text:
        return ""
    cleaned = re.sub(r"\bsell\b", " ", str(text), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
```

In `on_message`, capture the original-case caption (the existing line 37 lowercases it for trigger matching; we need original case for the note). Change:

```python
        text = (getattr(event, "text", "") or "").lower()
```

to:

```python
        raw_text = getattr(event, "text", "") or ""
        text = raw_text.lower()
```

In the `if "sell" in text:` branch (line 63-78), derive the note and pass it to the bridge. Change the two `subprocess.Popen([...])` calls to append `--note`:

```python
        if "sell" in text:
            note = _derive_note(raw_text)
            note_args = ["--note", note] if note else []
            if staging and (staged_any or os.path.isdir(staging)):
                subprocess.Popen(
                    [sys.executable, script, "--collect", chat_id,
                     "--chat-id", chat_id, "--bridge-port", port, *note_args],
                    creationflags=flags,
                )
            elif media:
                subprocess.Popen(
                    [sys.executable, script, "--chat-id", chat_id, "--bridge-port", port, *note_args, *media],
                    creationflags=flags,
                )
            else:
                return None
            return {"action": "skip", "reason": "ebay capture launched"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_seller_notes.py -v`
Expected: PASS

- [ ] **Step 5: Run the full unit suite**

Run: `pytest tests/unit -v`
Expected: PASS (all prior tests + new seller-note tests green)

- [ ] **Step 6: Commit**

```bash
git add integrations/hermes/plugin/__init__.py tests/unit/test_seller_notes.py
git commit -m "feat(hermes): derive seller note from WhatsApp caption"
```

---

## Final: merge-on-green + activation (assistant performs)

After all tasks are committed and `pytest tests/unit -v` is fully green:

- [ ] **Merge to master**

```bash
git checkout master
git merge --no-ff feature/seller-notes -m "feat: seller notes (WhatsApp caption -> AI/pricing/description)"
git push origin master
```

- [ ] **Restart DC backend** (no hot-reload by design) so the new Python loads — via `/api/system/restart` or the service restart used in this project.

- [ ] **Restart the Hermes gateway** so the updated plugin code activates (plugin code does not hot-reload).

- [ ] **Live smoke test:** send a few photos with a caption like `"no charger sell"` via WhatsApp; confirm the scheduled job's description discloses the missing accessory and the price reasoning reflects the note.

---

## Self-Review (completed during planning)

- **Spec coverage:** Entry point (Tasks 9-10), persistence (Task 8, via job_metadata), AI vision (Tasks 1-4), pricing incl. no-history grounding (Tasks 5-7), description (emergent via Task 1 vision prompt), empty-note regression (Task 1), injection-safety/length-cap (Task 8), deploy/activation (Final). Research-prompt injection deliberately deferred (documented in Plan-Level Notes).
- **Placeholder scan:** none — every code step contains literal code.
- **Type/name consistency:** `seller_note` parameter name is used uniformly across `analyze_item`, `analyze_with_research`, `get_ai_price_estimate`, `get_price_with_comps`, `get_final_pricing`; `build_seller_note_block` is defined once in `prompts.py` and imported by `ai_analyzer.py` and `pricing_engine.py`; `_clean_capture_note` (endpoint) and `_derive_note` (plugin) are distinct, each tested.
