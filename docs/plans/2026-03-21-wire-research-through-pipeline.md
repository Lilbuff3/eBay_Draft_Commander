# Wire Research Data Through Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop discarding AI research data — wire Phase 2 web research results into title generation, pricing, descriptions, aspect enrichment, and persist pricing comps for user inspection.

**Architecture:** The pipeline already runs 3 AI phases (vision → web research → specifics mapping). Phase 2 produces rich data (product name, market price, availability, compatibility, specs, sources) that currently only feeds item specifics. This plan wires that data into every downstream consumer: title selection, pricing engine, description rendering, and aspect enrichment.

**Tech Stack:** Python, Gemini API (google-genai SDK), Flask, existing pipeline services

---

## Task 1: Use Phase 3 SEO Title Instead of Phase 1 Title

**Files:**
- Modify: `backend/app/services/listing_ai_agent.py:97`
- Test: `tests/unit/test_listing_ai_agent.py` (create)

**Context:** Phase 1 generates `suggested_title` from vision only. Phase 3 calls `mapper.generate_seo_title()` which uses web-researched brand/model/MPN and stores it in `ai_data['seo_title']`. But `listing_ai_agent.py:97` reads `listing_data.get('suggested_title')` (Phase 1) and never checks `ai_data.get('seo_title')` (Phase 3).

**Step 1: Write the failing test**

Create `tests/unit/test_title_selection.py`:

```python
"""Test that research-enhanced SEO title is preferred over vision-only title."""
import pytest
from unittest.mock import patch, MagicMock


class TestTitleSelection:
    """Verify title priority: user_title > seo_title > suggested_title."""

    def test_seo_title_preferred_over_suggested(self):
        """When Phase 3 produces seo_title, it should be used over Phase 1 suggested_title."""
        from backend.app.services.listing_ai_agent import ListingAIAgent

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent.ai_analyzer = MagicMock()
        agent.pricing_engine = MagicMock()
        agent._default_shipping_cost = 6.50

        # Simulate AI data with both titles
        ai_data = {
            'listing': {
                'suggested_title': 'Generic Vision Title',
                'confidence_score': 0.9,
            },
            'seo_title': 'Aiwa CA-30 Boombox Stereo Receiver Cassette Radio Used',
            'identification': {'brand': 'Aiwa', 'model': 'CA-30'},
            'item_specifics': {},
        }
        agent.ai_analyzer.analyze_with_research = MagicMock(return_value=ai_data)

        job = MagicMock()
        job.ai_data = None  # Force re-analysis
        job.user_title = None
        job.user_description = None
        job.user_price = None
        job.folder_path = '/tmp/test'

        with patch('backend.app.services.listing_ai_agent.get_category_suggestions', return_value=''):
            result = agent.analyze_item(job, images=['/tmp/img.jpg'])

        assert result['success']
        assert result['title'] == 'Aiwa CA-30 Boombox Stereo Receiver Cassette Radio Used'

    def test_user_title_overrides_seo_title(self):
        """User-provided title always wins."""
        from backend.app.services.listing_ai_agent import ListingAIAgent

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent.ai_analyzer = MagicMock()
        agent.pricing_engine = MagicMock()
        agent._default_shipping_cost = 6.50

        ai_data = {
            'listing': {'suggested_title': 'Vision Title', 'confidence_score': 0.9},
            'seo_title': 'SEO Title',
            'identification': {},
            'item_specifics': {},
        }
        agent.ai_analyzer.analyze_with_research = MagicMock(return_value=ai_data)

        job = MagicMock()
        job.ai_data = None
        job.user_title = 'My Custom Title'
        job.user_description = None
        job.user_price = None
        job.folder_path = '/tmp/test'

        with patch('backend.app.services.listing_ai_agent.get_category_suggestions', return_value=''):
            result = agent.analyze_item(job, images=['/tmp/img.jpg'])

        assert result['title'] == 'My Custom Title'

    def test_falls_back_to_suggested_when_no_seo(self):
        """When Phase 3 doesn't produce seo_title, fall back to Phase 1."""
        from backend.app.services.listing_ai_agent import ListingAIAgent

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent.ai_analyzer = MagicMock()
        agent.pricing_engine = MagicMock()
        agent._default_shipping_cost = 6.50

        ai_data = {
            'listing': {'suggested_title': 'Vision Title', 'confidence_score': 0.9},
            'identification': {},
            'item_specifics': {},
        }
        agent.ai_analyzer.analyze_with_research = MagicMock(return_value=ai_data)

        job = MagicMock()
        job.ai_data = None
        job.user_title = None
        job.user_description = None
        job.user_price = None
        job.folder_path = '/tmp/test'

        with patch('backend.app.services.listing_ai_agent.get_category_suggestions', return_value=''):
            result = agent.analyze_item(job, images=['/tmp/img.jpg'])

        assert result['title'] == 'Vision Title'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_title_selection.py -v`
Expected: `test_seo_title_preferred_over_suggested` FAILS (gets 'Generic Vision Title' instead of SEO title)

**Step 3: Implement the fix**

In `backend/app/services/listing_ai_agent.py`, change line 97:

```python
# Before:
title = job_obj.user_title or listing_data.get('suggested_title')

# After:
title = job_obj.user_title or ai_data.get('seo_title') or listing_data.get('suggested_title')
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_title_selection.py -v`
Expected: 3/3 PASS

**Step 5: Commit**

```bash
git add backend/app/services/listing_ai_agent.py tests/unit/test_title_selection.py
git commit -m "fix: prefer research-enhanced SEO title over vision-only title"
```

---

## Task 2: Pass Research Market Price to Pricing Engine

**Files:**
- Modify: `backend/app/services/listing_ai_agent.py:125-159` (get_final_pricing)
- Modify: `backend/app/services/pricing_engine.py:567` (get_price_with_comps signature)

**Context:** Phase 2 research discovers `market_price: {low, mid, high}` from web sources. This is stored in `ai_data['research']['market_price']`. But `get_final_pricing()` doesn't pass it to `get_price_with_comps()`, so Strategy 3 fires a duplicate Gemini grounding call to rediscover the same data.

**Step 1: Write the failing test**

Add to `tests/unit/test_title_selection.py` (rename file later or create new):

```python
class TestResearchPricePassthrough:
    """Verify research market price is passed to pricing engine."""

    def test_research_price_passed_to_pricing(self):
        """When research found market_price, it should be passed to pricing engine."""
        from backend.app.services.listing_ai_agent import ListingAIAgent
        from unittest.mock import call

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent.pricing_engine = MagicMock()
        agent.pricing_engine.get_price_with_comps.return_value = {
            'suggested_price': 64.99, 'comps': [], 'reasoning': 'test'
        }
        agent._default_shipping_cost = 6.50

        result = agent.get_final_pricing(
            title='Aiwa CA-30',
            condition='USED_GOOD',
            ai_suggested_price=50.0,
            user_price=None,
            shipping_cost=6.50,
            identification={'brand': 'Aiwa', 'model': 'CA-30'},
            research_market_price={'low': 45, 'mid': 75, 'high': 120},
        )

        # Verify research_market_price was passed through
        call_kwargs = agent.pricing_engine.get_price_with_comps.call_args
        assert 'research_market_price' in call_kwargs.kwargs or \
               len(call_kwargs.args) > 6  # positional fallback
```

**Step 2: Run to verify failure**

Run: `pytest tests/unit/test_title_selection.py::TestResearchPricePassthrough -v`
Expected: FAIL (get_final_pricing doesn't accept research_market_price kwarg yet)

**Step 3: Implement**

In `backend/app/services/listing_ai_agent.py`, update `get_final_pricing` signature and call:

```python
def get_final_pricing(self, title, condition, ai_suggested_price, user_price,
                      shipping_cost=None, log_callback=None, identification=None,
                      research_market_price=None):
    # ... existing code ...
    price_result = self.pricing_engine.get_price_with_comps(
        title,
        condition=condition,
        ai_suggested_price=ai_suggested_price,
        shipping_cost=resolved_shipping,
        identification=identification,
        research_market_price=research_market_price,
    )
```

In `backend/app/services/pricing_engine.py`, update `get_price_with_comps` to accept and use `research_market_price`:

```python
def get_price_with_comps(self, title, ..., research_market_price=None):
    # Before Strategy 3, check if research already found price
    if research_market_price and research_market_price.get('mid'):
        mid = float(research_market_price['mid'])
        # Apply condition multiplier and shipping
        adjusted = self._apply_condition_multiplier(mid, condition)
        if shipping_cost > 0:
            adjusted = round(adjusted + shipping_cost, 2)
        adjusted = self._smart_round_99(adjusted)
        logger.info(f"   [PRICE] Research price: ${adjusted:.2f} (from Phase 2 market research)")
        return {
            "suggested_price": adjusted,
            "comps": [],
            "reasoning": f"Phase 2 research: ${research_market_price['low']}-${research_market_price['high']} range",
            "source": "research_market_price",
            "research_link": research_link
        }
```

Insert this block BEFORE Strategy 3 (Gemini Grounding) at line ~695.

In `backend/app/services/processor_service.py`, update the `get_final_pricing` call (~line 329) to pass research data:

```python
research_market_price = ai_data.get('research', {}).get('market_price')
pricing_result = self.ai_agent.get_final_pricing(
    analysis['title'], condition, analysis['ai_suggested_price'],
    job_obj.user_price, shipping_cost=shipping_cost,
    log_callback=log_callback, identification=ai_data.get('identification'),
    research_market_price=research_market_price,
)
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_title_selection.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/services/listing_ai_agent.py backend/app/services/pricing_engine.py backend/app/services/processor_service.py tests/unit/test_title_selection.py
git commit -m "feat: pass Phase 2 research market price to pricing engine, skip duplicate grounding"
```

---

## Task 3: Use Research Availability in Pricing Logic

**Files:**
- Modify: `backend/app/services/pricing_engine.py` (calculate_suggested_price)
- Modify: `backend/app/services/listing_ai_agent.py` (pass availability)
- Modify: `backend/app/services/processor_service.py` (pass availability)

**Context:** Phase 2 returns `availability: "common"|"moderate"|"rare"|"very_rare"`. Rare items get pulled toward market median, systematically underpricing them. When availability is "rare" or "very_rare", the pricing engine should use the high end of comps instead of median.

**Step 1: Write failing test**

```python
class TestAvailabilityPricing:
    def test_rare_item_uses_higher_price(self):
        """Rare items should price at 75th percentile, not median."""
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine.__new__(PricingEngine)
        engine.ai_client = None

        # Mock comps: prices 20, 40, 60, 80, 100
        comps = [{'price': p, 'condition': 'Used'} for p in [20, 40, 60, 80, 100]]

        normal_price = engine.calculate_suggested_price(comps, 'USED_GOOD', 0, 0)
        rare_price = engine.calculate_suggested_price(comps, 'USED_GOOD', 0, 0, availability='rare')

        assert rare_price['suggested_price'] > normal_price['suggested_price']
```

**Step 2: Run to verify failure**

Expected: FAIL (calculate_suggested_price doesn't accept availability kwarg)

**Step 3: Implement**

In `pricing_engine.py`, update `calculate_suggested_price` to accept `availability` and use 75th percentile for rare items:

```python
def calculate_suggested_price(self, comps, condition, acquisition_cost=0, shipping_cost=0, availability=None):
    # ... existing median logic ...

    # Rarity adjustment: rare items use 75th percentile instead of median
    if availability in ('rare', 'very_rare'):
        prices = sorted([c['price'] for c in comps])
        idx = int(len(prices) * 0.75)
        base_price = prices[min(idx, len(prices) - 1)]
        reasoning_prefix = "75th pctl (rare item)"
    else:
        base_price = median_price
        reasoning_prefix = "Median"
```

Thread `availability` through `get_final_pricing()` and `get_price_with_comps()` the same way as Task 2.

In `processor_service.py`, extract and pass:
```python
availability = ai_data.get('research', {}).get('availability')
```

**Step 4: Run tests, Step 5: Commit**

```bash
git commit -m "feat: rare/very_rare items use 75th percentile pricing instead of median"
```

---

## Task 4: Wire Research Data into Description Template

**Files:**
- Modify: `backend/app/services/processor_service.py:362` (_render_listing_template)
- Modify: `backend/app/services/template_manager.py` (render_description)

**Context:** `generate_html_description()` in `item_specifics_mapper.py` already builds professional descriptions using research notes, compatibility, and specs — but it's dead code. Rather than calling that (it's B2B-focused), we should pass research data to the existing template renderer so it can enrich the description with web-sourced details.

**Step 1: Write failing test**

```python
class TestDescriptionEnrichment:
    def test_research_notes_appear_in_description(self):
        """Research notes should be included in rendered description."""
        # Test that when research data is passed, the description template
        # includes compatibility and notes sections
```

**Step 2: Implement**

In `processor_service.py`, pass research data to the template:

```python
research = (job_obj.ai_data or {}).get('research', {})
template = self._render_listing_template(
    analysis['title'], analysis['raw_description'], upload_urls,
    analysis['item_specifics'], condition, research=research
)
```

In `_render_listing_template`, accept `research=None` and append research-sourced sections to the HTML:

```python
def _render_listing_template(self, title, description, image_urls,
                              item_specifics, condition, research=None):
    # ... existing template rendering ...

    # Append research-sourced sections if available
    if research:
        sections = []
        if research.get('compatible_with'):
            compat_list = ''.join(f'<li>{c}</li>' for c in research['compatible_with'][:6])
            sections.append(f'<h3>Compatible With</h3><ul>{compat_list}</ul>')
        if research.get('notes'):
            sections.append(f'<p><em>{research["notes"]}</em></p>')
        if sections:
            html += '\n'.join(sections)
```

**Step 3: Run tests, Step 4: Commit**

```bash
git commit -m "feat: enrich listing descriptions with web research data"
```

---

## Task 5: Pass Research Specs to Aspect Enrichment Prompt

**Files:**
- Modify: `backend/app/core/prompts.py:93` (ASPECT_ENRICHMENT_PROMPT)
- Modify: `backend/app/services/ai_analyzer.py:280` (enrich_item_specifics)
- Modify: `backend/app/services/processor_service.py:303` (caller)

**Context:** The aspect enrichment prompt tells Gemini to use "images and your knowledge." But Phase 2 already found web-verified specifications. Passing these as ground truth reduces hallucination.

**Step 1: Update the prompt**

In `prompts.py`, add a `{research_specs}` section to `ASPECT_ENRICHMENT_PROMPT`:

```python
ASPECT_ENRICHMENT_PROMPT = """You are filling in eBay item specifics for a product listing.

The item has already been identified as:
- Title: {title}
- Brand: {brand}
- Model: {model}
- MPN: {mpn}
- Category: {category_name}

{research_specs_section}

Below are the REQUIRED and RECOMMENDED item specifics...
```

Where `{research_specs_section}` is either empty or:
```
WEB-VERIFIED SPECIFICATIONS (use these as ground truth):
- Voltage: 120V
- Interface: USB 3.0
...
```

**Step 2: Update enrich_item_specifics signature**

```python
def enrich_item_specifics(self, image_paths, title, identification,
                           category_name, aspect_schema, existing_specifics,
                           research_specs=None):
```

Format `research_specs` dict into the prompt section.

**Step 3: Update caller in processor_service.py**

```python
research_specs = (job_obj.ai_data or {}).get('research', {}).get('specifications')
enriched_specifics = self.ai_agent.ai_analyzer.enrich_item_specifics(
    ..., research_specs=research_specs
)
```

**Step 4: Commit**

```bash
git commit -m "feat: pass web-verified specs to aspect enrichment prompt"
```

---

## Task 6: Persist Pricing Comps to Job Data

**Files:**
- Modify: `backend/app/services/listing_ai_agent.py:150-158` (get_final_pricing return)
- Modify: `backend/app/services/processor_service.py` (persist comps)

**Context:** `get_price_with_comps()` returns up to 5 comparable sales with titles, prices, and conditions. `get_final_pricing()` strips this, returning only `{price, timing}`. Users can't see what drove the price.

**Step 1: Implement**

In `listing_ai_agent.py`, return comps from `get_final_pricing`:

```python
return {
    "price": final_price,
    "timing": time.time() - pricing_start,
    "comps": price_result.get('comps', []),
    "reasoning": price_result.get('reasoning', ''),
    "source": price_result.get('source', ''),
}
```

In `processor_service.py`, persist to ai_data after pricing:

```python
ai_data['pricing_comps'] = pricing_result.get('comps', [])
ai_data['pricing_reasoning'] = pricing_result.get('reasoning', '')
ai_data['pricing_source'] = pricing_result.get('source', '')
job_obj.ai_data = ai_data
```

**Step 2: Commit**

```bash
git commit -m "feat: persist pricing comps and reasoning to job data"
```

---

## Task 7: Use Alt Part Numbers as Pricing Fallback

**Files:**
- Modify: `backend/app/services/pricing_engine.py` (Strategy 1.5 section)

**Context:** `item_specifics['Alternative Part Number']` contains superseded part numbers from research. When primary MPN has no sales data, try alternatives before falling through to keyword search.

**Step 1: Implement**

In `pricing_engine.py`, after Strategy 1.5 MPN search fails, try alternative part numbers:

```python
# Strategy 1.5b: Alternative part numbers
alt_pns = identification.get('alternative_part_numbers', [])
if not alt_pns:
    alt_pns = identification.get('oem_part_numbers', [])
for alt_pn in alt_pns[:3]:  # Try up to 3
    logger.info(f"[SEARCH] Alt part number: {alt_pn}...")
    sold_items = self.search_finding_api(f"{brand} {alt_pn}", category_id, limit=10)
    if sold_items:
        price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost)
        return { ... source: "market_data_alt_pn" ... }
```

**Step 2: Commit**

```bash
git commit -m "feat: try alternative part numbers as pricing search fallback"
```

---

## Task 8: Run Full Pipeline Integration Test

**Files:**
- Run: `tests/integration/test_full_pipeline.py`

**Step 1: Clean up previous test listings**

```bash
python -m pytest tests/integration/test_full_pipeline.py::TestCleanup -v -s
```

**Step 2: Run all 3 fixtures end-to-end**

```bash
python -m pytest tests/integration/test_full_pipeline.py::TestFullAIPipeline -v -s
```

**Step 3: Verify results logger captured improvements**

```python
from backend.app.core.results_logger import compare_last_runs
changes = compare_last_runs()
# Should show title changes (SEO titles now), possibly price changes
```

**Step 4: Verify on eBay**

Check the 3 scheduled listings in Seller Hub — titles should now be research-informed.

**Step 5: Final commit**

```bash
git commit -m "test: verify full pipeline with research data wired through"
```

---

## Execution Order

Tasks 1-6 are independent and can be parallelized. Task 7 is independent. Task 8 is the integration verification that runs after all others.

**Critical path:** Task 1 (title) → Task 8 (verify) is the minimum viable improvement.

**Recommended batch order:**
- Batch 1: Tasks 1, 2, 6 (low risk, high impact)
- Batch 2: Tasks 3, 5 (medium complexity)
- Batch 3: Tasks 4, 7 (description + alt PNs)
- Batch 4: Task 8 (integration verification)
