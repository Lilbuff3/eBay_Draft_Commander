# Pricing & Item Specifics Accuracy Improvements

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix two critical pipeline problems — (1) pricing falling through to AI estimate returning the same price for everything, and (2) item specifics not being populated — by adding eBay Finding API for real sold data and a two-pass AI specifics enrichment.

**Architecture:** Three independent fixes applied surgically. Fix 1 adds a `search_finding_api()` method to `PricingEngine` that calls eBay's `findCompletedItems` for actual sold prices, inserted as the primary search before the existing Browse API fallback. Fix 2 adds a second Gemini call in `processor_service.py` after category/aspects are known, passing the required aspect schema to the AI so it can fill them in. Fix 3 improves search query construction by trying multiple query strategies (brand+mpn, brand+model, then title keywords) instead of just "first 8 words."

**Tech Stack:** Python 3, Flask, eBay Finding API (XML), Google Gemini API, pytest

---

## Task 1: Add eBay Finding API Sold Search to PricingEngine

The Browse API only searches **active listings** (asking prices). The Finding API's `findCompletedItems` returns **actual sold prices** from the last 90 days — the gold standard for pricing.

**Files:**
- Modify: `backend/app/services/pricing_engine.py` (add `search_finding_api()` method)
- Test: `tests/unit/test_pricing_engine.py`

**Step 1: Write the failing test for Finding API search**

Add to `tests/unit/test_pricing_engine.py`:

```python
# ---------------------------------------------------------------------------
# TestFindingAPISoldSearch
# ---------------------------------------------------------------------------

class TestFindingAPISoldSearch:
    """Finding API returns actual sold prices (not asking prices)."""

    def test_finding_api_returns_sold_items(self, engine):
        """Successful Finding API call returns list of sold item dicts."""
        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <findCompletedItemsResponse xmlns="https://svcs.ebay.com/services/search/FindingService/v1">
            <ack>Success</ack>
            <searchResult count="2">
                <item>
                    <title>Xerox 108R00713 Solid Ink Cyan</title>
                    <sellingStatus>
                        <currentPrice currencyId="USD">45.00</currentPrice>
                        <sellingState>EndedWithSales</sellingState>
                    </sellingStatus>
                    <condition><conditionDisplayName>Used</conditionDisplayName></condition>
                    <listingInfo><endTime>2026-03-10T12:00:00.000Z</endTime></listingInfo>
                    <viewItemURL>https://www.ebay.com/itm/123</viewItemURL>
                </item>
                <item>
                    <title>Xerox 108R00713 Solid Ink Cyan OEM</title>
                    <sellingStatus>
                        <currentPrice currencyId="USD">52.00</currentPrice>
                        <sellingState>EndedWithSales</sellingState>
                    </sellingStatus>
                    <condition><conditionDisplayName>New</conditionDisplayName></condition>
                    <listingInfo><endTime>2026-03-08T15:30:00.000Z</endTime></listingInfo>
                    <viewItemURL>https://www.ebay.com/itm/456</viewItemURL>
                </item>
            </searchResult>
        </findCompletedItemsResponse>"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.text = mock_xml
            items = engine.search_finding_api("Xerox 108R00713")
        assert len(items) == 2
        assert items[0]["price"] == 45.00
        assert items[0]["condition"] == "Used"
        assert items[1]["price"] == 52.00

    def test_finding_api_filters_unsold(self, engine):
        """Items that ended without a sale (EndedWithoutSales) are excluded."""
        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <findCompletedItemsResponse xmlns="https://svcs.ebay.com/services/search/FindingService/v1">
            <ack>Success</ack>
            <searchResult count="2">
                <item>
                    <title>Good Item</title>
                    <sellingStatus>
                        <currentPrice currencyId="USD">30.00</currentPrice>
                        <sellingState>EndedWithSales</sellingState>
                    </sellingStatus>
                    <condition><conditionDisplayName>Used</conditionDisplayName></condition>
                    <listingInfo><endTime>2026-03-10T12:00:00.000Z</endTime></listingInfo>
                    <viewItemURL>https://www.ebay.com/itm/789</viewItemURL>
                </item>
                <item>
                    <title>Unsold Item</title>
                    <sellingStatus>
                        <currentPrice currencyId="USD">99.00</currentPrice>
                        <sellingState>EndedWithoutSales</sellingState>
                    </sellingStatus>
                    <condition><conditionDisplayName>New</conditionDisplayName></condition>
                    <listingInfo><endTime>2026-03-09T12:00:00.000Z</endTime></listingInfo>
                    <viewItemURL>https://www.ebay.com/itm/000</viewItemURL>
                </item>
            </searchResult>
        </findCompletedItemsResponse>"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.text = mock_xml
            items = engine.search_finding_api("Test Item")
        assert len(items) == 1
        assert items[0]["title"] == "Good Item"

    def test_finding_api_empty_on_no_app_id(self, monkeypatch):
        """Returns empty list if EBAY_APP_ID is missing."""
        monkeypatch.delenv("EBAY_APP_ID", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        eng = PricingEngine()
        assert eng.search_finding_api("anything") == []

    def test_finding_api_empty_on_network_error(self, engine):
        """Returns empty list on network failure (no crash)."""
        with patch("requests.get", side_effect=Exception("Network error")):
            items = engine.search_finding_api("Test")
        assert items == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pricing_engine.py::TestFindingAPISoldSearch -v`
Expected: FAIL with `AttributeError: 'PricingEngine' object has no attribute 'search_finding_api'`

**Step 3: Implement `search_finding_api()` in PricingEngine**

Add this method to `backend/app/services/pricing_engine.py` in the `PricingEngine` class, after the existing `search_sold_listings()` method (after line 170):

```python
    def search_finding_api(self, keywords: str, category_id: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Search eBay Finding API for ACTUALLY SOLD items (last 90 days).

        Unlike Browse API (active listings / asking prices), Finding API
        findCompletedItems returns real transaction data — what buyers paid.

        Args:
            keywords: Search query
            category_id: Optional eBay category ID
            limit: Max results (1-100)

        Returns:
            List of dicts with: title, price, condition, end_date, url
        """
        if not self.app_id:
            return []

        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.13.0",
            "SECURITY-APPNAME": self.app_id,
            "RESPONSE-DATA-FORMAT": "XML",
            "REST-PAYLOAD": "",
            "keywords": keywords,
            "paginationInput.entriesPerPage": str(min(limit, 100)),
            # Only sold items (not ended-without-sale)
            "itemFilter(0).name": "SoldItemsOnly",
            "itemFilter(0).value": "true",
            # USD only
            "itemFilter(1).name": "Currency",
            "itemFilter(1).value": "USD",
            # Sort by end time (most recent first)
            "sortOrder": "EndTimeSoonest",
        }

        if category_id:
            params["categoryId"] = category_id

        try:
            import xml.etree.ElementTree as ET

            response = requests.get(self.FINDING_API_URL, params=params, timeout=15)

            if response.status_code != 200:
                logger.warning(f"Finding API HTTP {response.status_code}")
                return []

            # Parse XML response
            ns = {"ns": "https://svcs.ebay.com/services/search/FindingService/v1"}
            root = ET.fromstring(response.text)

            ack = root.findtext("ns:ack", default="Failure", namespaces=ns)
            if ack != "Success":
                error_msg = root.findtext(".//ns:errorMessage/ns:error/ns:message", default="Unknown", namespaces=ns)
                logger.warning(f"Finding API error: {error_msg}")
                return []

            sold_items = []
            for item_el in root.findall(".//ns:searchResult/ns:item", namespaces=ns):
                try:
                    title = item_el.findtext("ns:title", default="", namespaces=ns)

                    # Only include items that actually sold
                    selling_state = item_el.findtext(
                        "ns:sellingStatus/ns:sellingState", default="", namespaces=ns
                    )
                    if selling_state != "EndedWithSales":
                        continue

                    price_str = item_el.findtext(
                        "ns:sellingStatus/ns:currentPrice", default="0", namespaces=ns
                    )
                    price = float(price_str)
                    if price <= 0:
                        continue

                    condition = item_el.findtext(
                        "ns:condition/ns:conditionDisplayName", default="Used", namespaces=ns
                    )
                    end_date = item_el.findtext(
                        "ns:listingInfo/ns:endTime", default="", namespaces=ns
                    )
                    url = item_el.findtext("ns:viewItemURL", default="", namespaces=ns)

                    sold_items.append({
                        "title": title,
                        "price": price,
                        "currency": "USD",
                        "condition": condition,
                        "end_date": end_date[:10] if end_date else "",
                        "url": url,
                    })
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Skipping Finding API item: {e}")
                    continue

            logger.info(f"Finding API returned {len(sold_items)} sold items for: {keywords[:50]}")
            return sold_items

        except Exception as e:
            logger.warning(f"Finding API request failed: {e}")
            return []
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_pricing_engine.py::TestFindingAPISoldSearch -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add backend/app/services/pricing_engine.py tests/unit/test_pricing_engine.py
git commit -m "feat: add Finding API search for real sold prices"
```

---

## Task 2: Wire Finding API Into the Pricing Cascade

Now insert `search_finding_api()` as the **primary** search method, with Browse API as fallback.

**Files:**
- Modify: `backend/app/services/pricing_engine.py:435-566` (`get_price_with_comps()` method)
- Test: `tests/unit/test_pricing_engine.py`

**Step 1: Write failing tests for the new cascade order**

Add to `tests/unit/test_pricing_engine.py`:

```python
class TestFindingAPIIntegration:
    """Finding API is tried first in the pricing cascade."""

    def test_finding_api_used_before_browse(self, engine):
        """Finding API results are used when available (skips Browse API)."""
        finding_items = [
            {"title": "Sold Item", "price": 40.0, "condition": "Used",
             "end_date": "2026-03-10", "url": "http://example.com", "currency": "USD"}
        ]
        with patch.object(engine, "search_finding_api", return_value=finding_items) as mock_finding, \
             patch.object(engine, "search_sold_listings") as mock_browse:
            result = engine.get_price_with_comps("Test Item")
        mock_finding.assert_called()
        mock_browse.assert_not_called()
        assert result["source"] == "market_data_sold"

    def test_fallback_to_browse_when_finding_empty(self, engine):
        """When Finding API returns nothing, Browse API is tried next."""
        browse_items = [
            {"title": "Active Item", "price": 35.0, "condition": "Used",
             "end_date": "Active", "url": "http://example.com"}
        ]
        with patch.object(engine, "search_finding_api", return_value=[]), \
             patch.object(engine, "search_sold_listings", return_value=browse_items):
            result = engine.get_price_with_comps("Test Item")
        assert result["source"] == "market_data"

    def test_finding_api_isbn_path(self, engine):
        """ISBN search also uses Finding API first."""
        finding_items = [
            {"title": "Book", "price": 25.0, "condition": "Good",
             "end_date": "2026-03-10", "url": "http://example.com", "currency": "USD"}
        ]
        with patch.object(engine, "search_finding_api", return_value=finding_items):
            result = engine.get_price_with_comps("Test Book", isbn="9780123456789")
        assert result["source"] == "market_data_isbn_sold"

    def test_finding_api_identifier_path(self, engine):
        """Identifier search (brand+mpn) also uses Finding API first."""
        finding_items = [
            {"title": "Xerox Part", "price": 55.0, "condition": "New",
             "end_date": "2026-03-10", "url": "http://example.com", "currency": "USD"}
        ]
        ident = {"brand": "Xerox", "mpn": "108R00713", "model": ""}
        with patch.object(engine, "search_finding_api", return_value=finding_items):
            result = engine.get_price_with_comps("Xerox Solid Ink", identification=ident)
        assert result["source"] == "market_data_id_sold"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_pricing_engine.py::TestFindingAPIIntegration -v`
Expected: FAIL — `search_finding_api` not called by `get_price_with_comps` yet

**Step 3: Modify `get_price_with_comps()` to try Finding API first**

In `backend/app/services/pricing_engine.py`, modify `get_price_with_comps()`. The pattern is: for each search strategy (ISBN, ID, keyword), try Finding API first, then fall back to Browse API.

Replace the method body of `get_price_with_comps` (lines 435-565) with:

```python
    def get_price_with_comps(self, title: str, condition: str = "Used - Good", category_id: Optional[str] = None, ai_suggested_price: Optional[str] = None, acquisition_cost: float = 0.0, isbn: Optional[str] = None, shipping_cost: float = 0.0, identification: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point: Get suggested price and comparable sales data.

        Pricing cascade (in priority order):
        0. User override (handled by caller)
        1. ISBN search — Finding API (sold) -> Browse API (active)
        1.5. MPN/Model search — Finding API (sold) -> Browse API (active)
        2. Keyword search — Finding API (sold) -> Browse API (active)
        3. Gemini + Google Search grounding
        4. AI vision estimate (weakest signal)
        5. Fail loudly (returns None)
        """
        research_link = self.generate_ebay_search_link(title)

        # --- STRATEGY 1: ISBN SEARCH (Gold Standard for Books) ---
        if isbn:
            # Try Finding API (sold data) first
            logger.info(f"[SEARCH] ISBN sold search: {isbn}...")
            sold_items = self.search_finding_api(isbn, category_id, limit=15)
            if sold_items:
                price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost)
                logger.info(f"   [PRICE] Sold price (ISBN): ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                return {
                    "suggested_price": price_data["suggested_price"],
                    "comps": sold_items[:5],
                    "reasoning": f"ISBN Sold Match: {price_data['reasoning']}",
                    "projected_profit": price_data.get("projected_profit"),
                    "source": "market_data_isbn_sold",
                    "research_link": self.generate_ebay_search_link(isbn)
                }

            # Fallback: Browse API (active listings)
            logger.info(f"   [WARN] No sold data for ISBN, trying active listings...")
            sold_items = self.search_sold_listings(isbn, category_id, limit=15)
            if sold_items:
                price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost)
                logger.info(f"   [PRICE] Active price (ISBN): ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                return {
                    "suggested_price": price_data["suggested_price"],
                    "comps": sold_items[:5],
                    "reasoning": f"ISBN Match: {price_data['reasoning']}",
                    "projected_profit": price_data.get("projected_profit"),
                    "source": "market_data_isbn",
                    "research_link": self.generate_ebay_search_link(isbn)
                }
            logger.info("   [WARN] No sales found for ISBN, falling back to title...")

        # --- STRATEGY 1.5: MPN/MODEL SEARCH ---
        if identification:
            mpn = identification.get('mpn', '')
            brand = identification.get('brand', '')
            model = identification.get('model', '')

            id_parts = [p for p in [brand, mpn or model] if p]
            if id_parts and len(" ".join(id_parts)) >= 5:
                id_query = " ".join(id_parts)

                # Try Finding API (sold data) first
                logger.info(f"[SEARCH] Identifier sold search: {id_query}...")
                sold_items = self.search_finding_api(id_query, category_id, limit=15)
                if sold_items:
                    price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost)
                    logger.info(f"   [PRICE] Sold price (ID): ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                    return {
                        "suggested_price": price_data["suggested_price"],
                        "comps": sold_items[:5],
                        "reasoning": f"ID Sold Match ({id_query}): {price_data['reasoning']}",
                        "projected_profit": price_data.get("projected_profit"),
                        "source": "market_data_id_sold",
                        "research_link": self.generate_ebay_search_link(id_query)
                    }

                # Fallback: Browse API (active listings)
                logger.info(f"   [WARN] No sold data for identifiers, trying active listings...")
                sold_items = self.search_sold_listings(id_query, category_id, limit=15)
                if sold_items:
                    price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost)
                    logger.info(f"   [PRICE] Active price (ID): ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                    return {
                        "suggested_price": price_data["suggested_price"],
                        "comps": sold_items[:5],
                        "reasoning": f"ID Match ({id_query}): {price_data['reasoning']}",
                        "projected_profit": price_data.get("projected_profit"),
                        "source": "market_data_id",
                        "research_link": self.generate_ebay_search_link(id_query)
                    }
                logger.info("   [WARN] No sales found for identifiers, falling back to title...")

        # --- STRATEGY 2: KEYWORD SEARCH ---
        search_query = " ".join(title.split()[:8])

        # Try Finding API (sold data) first
        logger.info(f"[SEARCH] Keyword sold search: {search_query[:50]}...")
        sold_items = self.search_finding_api(search_query, category_id, limit=15)
        if sold_items:
            price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost)
            logger.info(f"   [PRICE] Sold price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
            return {
                "suggested_price": price_data["suggested_price"],
                "comps": sold_items[:5],
                "reasoning": f"Sold: {price_data['reasoning']}",
                "projected_profit": price_data.get("projected_profit"),
                "source": "market_data_sold",
                "research_link": research_link
            }

        # Fallback: Browse API (active listings)
        logger.info(f"   [WARN] No sold data, trying active listings: {search_query[:50]}...")
        sold_items = self.search_sold_listings(search_query, category_id, limit=15)
        if sold_items:
            price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost)
            logger.info(f"   [PRICE] Active price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
            return {
                "suggested_price": price_data["suggested_price"],
                "comps": sold_items[:5],
                "reasoning": price_data["reasoning"],
                "projected_profit": price_data.get("projected_profit"),
                "source": "market_data",
                "research_link": research_link
            }

        # --- STRATEGY 3: GEMINI GROUNDING ---
        logger.info(f"[SEARCH] Performing AI Market Research (Gemini Grounding)...")
        grounded_result = self.get_ai_price_estimate(title, condition)
        if grounded_result:
            ai_price = grounded_result['price']
            ai_reasoning = grounded_result.get('reasoning', "Researched via Gemini")
            if shipping_cost > 0:
                ai_price = round(ai_price + shipping_cost, 2)
                ai_reasoning += f" + ${shipping_cost:.2f} free shipping buffer"
            ai_price = self._smart_round_99(ai_price)
            logger.info(f"   [WEB] AI Research Price: ${ai_price:.2f}")
            return {
                "suggested_price": ai_price,
                "comps": [],
                "reasoning": ai_reasoning,
                "source": "ai_grounded_research",
                "research_link": research_link
            }

        # --- STRATEGY 4: AI VISION ESTIMATE ---
        if ai_suggested_price:
            fallback_price = float(ai_suggested_price)
            fallback_reasoning = "Based on logical inference from visual analysis (No market data found)"
            if shipping_cost > 0:
                fallback_price = round(fallback_price + shipping_cost, 2)
                fallback_reasoning += f" + ${shipping_cost:.2f} free shipping buffer"
            fallback_price = self._smart_round_99(fallback_price)
            logger.info(f"   [INFO] Using AI image estimate: ${fallback_price}")
            return {
                "suggested_price": fallback_price,
                "comps": [],
                "reasoning": fallback_reasoning,
                "source": "ai_estimate",
                "research_link": research_link
            }

        # --- STRATEGY 5: FAIL LOUDLY ---
        logger.warning("   [FAIL] Price discovery failed. Manual pricing required.")
        return {
            "suggested_price": None,
            "comps": [],
            "reasoning": "Could not determine price. Manual input required.",
            "source": "failed_requires_manual",
            "research_link": research_link,
            "error": "Price discovery failed"
        }
```

**Step 4: Run all pricing tests to verify everything passes**

Run: `pytest tests/unit/test_pricing_engine.py -v`
Expected: ALL tests PASS (existing + new)

**Step 5: Commit**

```bash
git add backend/app/services/pricing_engine.py tests/unit/test_pricing_engine.py
git commit -m "feat: wire Finding API as primary pricing source in cascade"
```

---

## Task 3: Two-Pass AI Specifics Enrichment

After the category is determined and the eBay aspect schema is fetched, make a second focused Gemini call that passes the **required aspect names and allowed values** to the AI so it can fill them in from the images.

**Files:**
- Modify: `backend/app/core/prompts.py` (add new prompt template)
- Modify: `backend/app/services/ai_analyzer.py` (add `enrich_item_specifics()` method)
- Modify: `backend/app/services/processor_service.py:289-302` (call enrichment after aspect schema fetch)
- Test: `tests/unit/test_item_specifics.py`

**Step 1: Add the enrichment prompt to `prompts.py`**

Add to the end of `backend/app/core/prompts.py`:

```python
ASPECT_ENRICHMENT_PROMPT = """You are filling in eBay item specifics for a product listing.

The item has already been identified as:
- Title: {title}
- Brand: {brand}
- Model: {model}
- MPN: {mpn}
- Category: {category_name}

Below are the REQUIRED and RECOMMENDED item specifics for this eBay category.
For each aspect, I've listed the allowed values (if constrained by eBay).

{aspect_list}

EXISTING SPECIFICS (already filled, do NOT overwrite unless empty):
{existing_specifics}

INSTRUCTIONS:
1. Using the product images and your knowledge of this product, fill in as many aspects as possible.
2. For aspects with allowed values, you MUST pick from the allowed list (exact match).
3. For free-text aspects, provide accurate values based on the images and product knowledge.
4. If you genuinely cannot determine a value, omit it (do NOT guess randomly).
5. Return ONLY a flat JSON object mapping aspect names to values.
6. Aspect values must be strings, max 65 characters each.
7. Do NOT include aspects you cannot determine.

Return JSON:
{{
    "Aspect Name": "Value",
    "Another Aspect": "Value"
}}"""
```

**Step 2: Add `enrich_item_specifics()` to AIAnalyzer**

Add to `backend/app/services/ai_analyzer.py` after the `analyze_item()` method (after line 230):

```python
    def enrich_item_specifics(self, image_paths: list, title: str, identification: dict,
                               category_name: str, aspect_schema: list,
                               existing_specifics: dict) -> dict:
        """
        Second-pass AI call: fill in item specifics using the eBay aspect schema.

        This is a lightweight text+image call that passes the category's required
        and optional aspects (with allowed values) so the AI can fill them in
        accurately instead of guessing generic fields.

        Args:
            image_paths: Original product images (reused from analysis)
            title: Item title
            identification: Dict with brand/model/mpn from first AI pass
            category_name: eBay category name
            aspect_schema: List of aspect dicts from taxonomy API
            existing_specifics: Already-filled specifics (won't be overwritten)

        Returns:
            Dict of aspect_name -> value (merged with existing)
        """
        if not self.client or not aspect_schema:
            return existing_specifics

        from backend.app.core.prompts import ASPECT_ENRICHMENT_PROMPT

        # Build the aspect list text for the prompt
        aspect_lines = []
        for aspect in aspect_schema:
            name = aspect.get('name', '')
            required = aspect.get('isRequired', False)
            values = aspect.get('values', [])

            tag = "REQUIRED" if required else "recommended"
            if values:
                # Show first 20 allowed values to keep prompt size reasonable
                val_str = ", ".join(values[:20])
                if len(values) > 20:
                    val_str += f" ... ({len(values)} total)"
                aspect_lines.append(f"- [{tag}] {name}: Allowed values: [{val_str}]")
            else:
                aspect_lines.append(f"- [{tag}] {name}: (free text)")

        aspect_list_text = "\n".join(aspect_lines)

        # Format existing specifics
        existing_text = "\n".join(
            f"- {k}: {v}" for k, v in existing_specifics.items() if v
        ) or "(none filled yet)"

        prompt = ASPECT_ENRICHMENT_PROMPT.format(
            title=title,
            brand=identification.get('brand', 'Unknown'),
            model=identification.get('model', ''),
            mpn=identification.get('mpn', ''),
            category_name=category_name,
            aspect_list=aspect_list_text,
            existing_specifics=existing_text,
        )

        # Build content with images (reuse from first pass)
        from PIL import Image as PILImage
        contents = [prompt]
        for path in image_paths[:4]:  # Limit to 4 images to keep call fast
            try:
                img = PILImage.open(path)
                contents.append(img)
            except Exception:
                continue

        try:
            limiter.wait_if_needed('gemini')

            config = types.GenerateContentConfig(
                temperature=0.1,  # Low temp for factual extraction
                max_output_tokens=2000,
                response_mime_type="application/json",
            )

            response = self.client.models.generate_content(
                model=AI_MODEL_NAME,
                contents=contents,
                config=config,
            )

            text = response.text.strip() if response.text else "{}"
            # Clean markdown wrappers
            if text.startswith('```json'):
                text = text.split('```json')[1].split('```')[0]
            elif text.startswith('```'):
                text = text.split('```')[1].split('```')[0]

            import json as json_mod
            enriched = json_mod.loads(text.strip())

            if not isinstance(enriched, dict):
                logger.warning("Aspect enrichment returned non-dict")
                return existing_specifics

            # Merge: existing specifics take priority (don't overwrite user data)
            merged = dict(existing_specifics)
            for key, value in enriched.items():
                if key not in merged or not merged[key]:
                    # Truncate to eBay max
                    merged[key] = str(value)[:65]

            logger.info(f"Aspect enrichment added {len(merged) - len(existing_specifics)} new specifics")
            return merged

        except Exception as e:
            logger.warning(f"Aspect enrichment failed (non-fatal): {e}")
            return existing_specifics
```

**Step 3: Write the failing test**

Add to `tests/unit/test_item_specifics.py` (or create if missing):

```python
"""Tests for two-pass item specifics enrichment."""
import pytest
from unittest.mock import patch, MagicMock


class TestAspectEnrichment:
    """AI enrichment fills in eBay-required aspects from images + schema."""

    def test_enrichment_merges_without_overwriting(self):
        """New aspects are added but existing ones are preserved."""
        from backend.app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        analyzer.client = None  # Disabled client returns existing

        existing = {"Brand": "Xerox", "MPN": "108R00713"}
        result = analyzer.enrich_item_specifics(
            image_paths=[], title="Test", identification={},
            category_name="Toner", aspect_schema=[], existing_specifics=existing,
        )
        assert result == existing  # No client -> passthrough

    def test_enrichment_returns_existing_on_empty_schema(self):
        """Empty aspect schema -> skip enrichment, return existing."""
        from backend.app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        analyzer.client = MagicMock()

        existing = {"Brand": "Test"}
        result = analyzer.enrich_item_specifics(
            image_paths=[], title="Test", identification={},
            category_name="", aspect_schema=[], existing_specifics=existing,
        )
        assert result == existing

    @patch("backend.app.services.ai_analyzer.limiter")
    def test_enrichment_adds_new_fields(self, mock_limiter):
        """When AI returns new aspects, they are merged in."""
        from backend.app.services.ai_analyzer import AIAnalyzer
        from unittest.mock import PropertyMock

        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        mock_client = MagicMock()
        analyzer.client = mock_client

        # Simulate AI returning new aspects
        mock_response = MagicMock()
        type(mock_response).text = PropertyMock(return_value='{"Color": "Cyan", "Brand": "Should Not Overwrite"}')
        mock_client.models.generate_content.return_value = mock_response

        existing = {"Brand": "Xerox"}
        schema = [
            {"name": "Color", "isRequired": True, "values": ["Cyan", "Magenta", "Yellow", "Black"]},
            {"name": "Brand", "isRequired": True, "values": []},
        ]

        result = analyzer.enrich_item_specifics(
            image_paths=[], title="Xerox Ink", identification={"brand": "Xerox"},
            category_name="Toner Cartridges", aspect_schema=schema, existing_specifics=existing,
        )
        assert result["Color"] == "Cyan"
        assert result["Brand"] == "Xerox"  # NOT overwritten

    @patch("backend.app.services.ai_analyzer.limiter")
    def test_enrichment_truncates_long_values(self, mock_limiter):
        """Values longer than 65 chars are truncated."""
        from backend.app.services.ai_analyzer import AIAnalyzer
        from unittest.mock import PropertyMock

        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        mock_client = MagicMock()
        analyzer.client = mock_client

        long_value = "A" * 100
        mock_response = MagicMock()
        type(mock_response).text = PropertyMock(return_value=f'{{"Type": "{long_value}"}}')
        mock_client.models.generate_content.return_value = mock_response

        schema = [{"name": "Type", "isRequired": False, "values": []}]
        result = analyzer.enrich_item_specifics(
            image_paths=[], title="Test", identification={},
            category_name="Test", aspect_schema=schema, existing_specifics={},
        )
        assert len(result["Type"]) == 65
```

**Step 4: Run tests to verify they fail (then pass after implementation)**

Run: `pytest tests/unit/test_item_specifics.py::TestAspectEnrichment -v`

**Step 5: Wire enrichment into processor_service.py**

In `backend/app/services/processor_service.py`, after the `_validate_and_enrich_specifics` call (around line 292), add the two-pass enrichment. Insert after line 292 (after `ebay_aspect_schema = self._validate_and_enrich_specifics(...)`):

```python
        # 4c. Two-pass AI enrichment: fill remaining required aspects using images + schema
        if ebay_aspect_schema and analysis.get('ai_data', {}).get('image_paths'):
            try:
                enriched_specifics = self.ai_agent.ai_analyzer.enrich_item_specifics(
                    image_paths=analysis['ai_data']['image_paths'][:4],
                    title=analysis['title'],
                    identification=analysis.get('ai_data', {}).get('identification', {}),
                    category_name=cat_result.get('name', ''),
                    aspect_schema=ebay_aspect_schema,
                    existing_specifics=analysis['item_specifics'],
                )
                analysis['item_specifics'] = enriched_specifics
                _log(f"Enriched to {len(enriched_specifics)} item specifics (two-pass)")
            except Exception as e:
                _log(f"Aspect enrichment skipped: {e}", level='warning')
```

**Step 6: Run full test suite**

Run: `pytest tests/unit/ -v`
Expected: ALL tests PASS

**Step 7: Commit**

```bash
git add backend/app/core/prompts.py backend/app/services/ai_analyzer.py backend/app/services/processor_service.py tests/unit/test_item_specifics.py
git commit -m "feat: two-pass AI enrichment fills eBay-required item specifics"
```

---

## Task 4: Smarter Search Query Construction

The current keyword search uses "first 8 words of title" which can include filler. Use structured identifiers when available.

**Files:**
- Modify: `backend/app/services/pricing_engine.py` (helper method for query building)
- Test: `tests/unit/test_pricing_engine.py`

**Step 1: Write failing test**

Add to `tests/unit/test_pricing_engine.py`:

```python
class TestSmartQueryConstruction:
    """Search queries should prioritize identifiers over raw title words."""

    def test_build_search_query_uses_brand_mpn(self):
        engine = PricingEngine.__new__(PricingEngine)
        query = engine._build_keyword_query(
            title="Genuine Xerox 108R00713 Solid Ink Cyan for Phaser 8560 OEM New",
            identification={"brand": "Xerox", "mpn": "108R00713", "model": "Phaser 8560"}
        )
        # Should prefer brand+mpn+product_type, not raw title truncation
        assert "Xerox" in query
        assert "108R00713" in query

    def test_build_search_query_fallback_to_title(self):
        engine = PricingEngine.__new__(PricingEngine)
        query = engine._build_keyword_query(
            title="Vintage Brass Compass Navigation Tool Antique Maritime",
            identification=None
        )
        # No identifiers -> uses first 8 words of title
        assert "Vintage" in query
        assert len(query.split()) <= 8

    def test_build_search_query_no_duplicate_brand(self):
        """If brand is already in the title fragment, don't double it."""
        engine = PricingEngine.__new__(PricingEngine)
        query = engine._build_keyword_query(
            title="Xerox 108R00713 Solid Ink",
            identification={"brand": "Xerox", "mpn": "108R00713", "model": ""}
        )
        # Brand should appear only once
        assert query.count("Xerox") == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pricing_engine.py::TestSmartQueryConstruction -v`
Expected: FAIL — `_build_keyword_query` does not exist

**Step 3: Implement `_build_keyword_query()` and wire it in**

Add to `PricingEngine` class in `backend/app/services/pricing_engine.py`:

```python
    def _build_keyword_query(self, title: str, identification: Optional[Dict] = None) -> str:
        """Build an optimized search query from identifiers or title.

        Priority:
        1. Brand + MPN (most precise, what buyers search by)
        2. Brand + Model (good fallback)
        3. First 8 words of title (last resort)
        """
        if identification:
            brand = identification.get('brand', '').strip()
            mpn = identification.get('mpn', '').strip()
            model = identification.get('model', '').strip()
            product_type = identification.get('product_type', '').strip()

            # Strategy: brand + mpn + product_type
            if brand and mpn:
                parts = [brand, mpn]
                if product_type and len(" ".join(parts + [product_type])) <= 60:
                    parts.append(product_type)
                return " ".join(parts)

            # Strategy: brand + model
            if brand and model:
                parts = [brand, model]
                if product_type and len(" ".join(parts + [product_type])) <= 60:
                    parts.append(product_type)
                return " ".join(parts)

        # Fallback: first 8 words of title
        return " ".join(title.split()[:8])
```

Then update the keyword search section of `get_price_with_comps()` to use it. Replace the line:

```python
        search_query = " ".join(title.split()[:8])
```

with:

```python
        search_query = self._build_keyword_query(title, identification)
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_pricing_engine.py -v`
Expected: ALL pass

**Step 5: Commit**

```bash
git add backend/app/services/pricing_engine.py tests/unit/test_pricing_engine.py
git commit -m "feat: smarter search query construction using identifiers"
```

---

## Task 5: Run Full Test Suite and Verify

**Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: ALL tests PASS (existing 144+ new tests)

**Step 2: Run frontend build to ensure no breakage**

Run: `cd frontend && npm run build`
Expected: Build succeeds (backend changes shouldn't affect frontend)

**Step 3: Commit any remaining fixes**

If any tests needed adjustment, commit fixes.

```bash
git add -A
git commit -m "chore: test fixes and cleanup after pricing/specifics improvements"
```

---

## Summary of Changes

| Fix | Problem | Solution | Files Changed |
|-----|---------|----------|---------------|
| **Finding API** | Pricing uses active listings (asking prices), items fall through to AI estimate | Add `findCompletedItems` for real sold prices as primary source | `pricing_engine.py` |
| **Two-Pass Specifics** | Only 4 generic fields populated (Brand/Model/MPN/Type) | Second Gemini call with category's required aspect schema | `ai_analyzer.py`, `processor_service.py`, `prompts.py` |
| **Smart Queries** | "First 8 words" includes filler, misses key identifiers | Build query from brand+mpn when available | `pricing_engine.py` |

**Expected impact:**
- Pricing: ~70-80% of items should now get real sold-price data instead of AI estimates
- Specifics: ~3-4x more fields filled per listing (from ~4 to ~12-15)
- Zero additional cost for Finding API (uses existing `EBAY_APP_ID`)
- One extra Gemini call per item for specifics (~1 RPM impact)
