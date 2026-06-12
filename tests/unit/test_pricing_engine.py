"""
Tests for PricingEngine — price calculation, comp strategies, Browse API cascade.
"""

import pytest
from unittest.mock import patch

from backend.app.services.pricing_engine import PricingEngine


@pytest.fixture
def engine(monkeypatch):
    """Create a PricingEngine without triggering the google genai import."""
    monkeypatch.setenv("EBAY_APP_ID", "test-app-id")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    return PricingEngine()


def _make_sold_items(prices):
    """Helper: build a minimal sold-items list from a sequence of prices."""
    return [
        {"title": f"Item {i}", "price": p, "condition": "Used", "end_date": "2024-01-01", "url": "http://example.com"}
        for i, p in enumerate(prices)
    ]


# ---------------------------------------------------------------------------
# TestCalculateSuggestedPrice
# ---------------------------------------------------------------------------


class TestCalculateSuggestedPrice:
    def test_median_calculation(self, engine):
        items = _make_sold_items([10, 20, 30, 40, 50])
        result = engine.calculate_suggested_price(items, our_condition="New")
        # median=30, no multiplier, price=30 -> >15 smart pricing -> floor(30)-0.01=29.99
        assert result["median_price"] == 30.0
        assert result["suggested_price"] == 29.99

    def test_no_multiplier_applied(self, engine):
        """Condition filtering happens at API level, not via multiplier."""
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="Used - Good")
        # No multiplier — base_price=100, smart pricing: floor(100)-0.01=99.99
        assert result["suggested_price"] == 99.99
        assert "multiplier" not in result

    def test_condition_does_not_affect_price(self, engine):
        """Different conditions should produce the same price from same comps."""
        items = _make_sold_items([100])
        result_new = engine.calculate_suggested_price(items, our_condition="New")
        result_used = engine.calculate_suggested_price(items, our_condition="Used - Good")
        assert result_new["suggested_price"] == result_used["suggested_price"]

    def test_empty_items_returns_none(self, engine):
        result = engine.calculate_suggested_price([])
        assert result["suggested_price"] is None
        assert result["comp_count"] == 0
        assert result["reasoning"] == "No comparable sales found"

    def test_zero_prices_filtered(self, engine):
        items = _make_sold_items([0, 0])
        result = engine.calculate_suggested_price(items)
        assert result["suggested_price"] is None
        assert result["reasoning"] == "No valid prices in comps"

    def test_shipping_buffer_applied(self, engine):
        items = _make_sold_items([40])
        result = engine.calculate_suggested_price(items, our_condition="New", shipping_cost=6.50)
        # base=40 + 6.50 = 46.50
        # smart pricing: floor(46.50)=46, cents=0.50 < 0.80 -> 46-0.01 = 45.99
        assert result["suggested_price"] == 45.99
        assert "shipping" in result["reasoning"]

    def test_smart_99_above_15(self, engine):
        items = _make_sold_items([45])
        result = engine.calculate_suggested_price(items, our_condition="New")
        # base=45.0 -> >15 -> floor(45)-0.01 = 44.99
        assert result["suggested_price"] == 44.99

    def test_no_smart_pricing_at_or_below_15(self, engine):
        items = _make_sold_items([10])
        result = engine.calculate_suggested_price(items, our_condition="New")
        # base=10.0 -> NOT > 15 -> stays 10.0
        assert result["suggested_price"] == 10.0

    def test_margin_boost_triggered(self, engine):
        items = _make_sold_items([40])
        result = engine.calculate_suggested_price(
            items, our_condition="Used - Good", acquisition_cost=50, shipping_cost=6.50
        )
        # base=40 + 6.50 = 46.50
        # est_fees = 46.50*0.1325 + 0.30 = 6.16 + 0.30 = 6.46
        # projected_profit = 46.50 - 6.46 - 50 - 6.50 = -16.46 (< 10)
        # target_price = (50 + 10 + 0.30) / (1 - 0.1325) = 60.30 / 0.8675 = 69.51...
        # margin_boost=True -> smart pricing: floor(69.51)=69, cents=0.51 < 0.80 -> 68.99
        assert result["suggested_price"] == 68.99
        assert "Boosted" in result["reasoning"]

    def test_no_margin_boost_zero_acquisition(self, engine):
        items = _make_sold_items([10])
        result = engine.calculate_suggested_price(items, our_condition="Used - Good")
        # acquisition_cost=0 (default) -> no boost
        assert "Boosted" not in result["reasoning"]


# ---------------------------------------------------------------------------
# TestGetPriceWithComps
# ---------------------------------------------------------------------------


class TestGetPriceWithComps:
    _sold = [
        {"title": "Test Item", "price": 25.0, "condition": "Good", "end_date": "2024-01-01", "url": "http://example.com"}
    ]

    def test_isbn_search_succeeds(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=self._sold):
            result = engine.get_price_with_comps("Test Book", isbn="1234567890")
        assert result["source"] == "market_data_isbn"
        assert result["suggested_price"] is not None

    def test_isbn_fallback_to_keyword(self, engine):
        # ISBN search returns empty, keyword search returns items
        with patch.object(engine, "search_sold_listings", side_effect=[[], self._sold]):
            result = engine.get_price_with_comps("Test Book", isbn="1234567890")
        assert result["source"] == "market_data_keyword"

    def test_keyword_search_succeeds(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=self._sold):
            result = engine.get_price_with_comps("Test Item Title")
        assert result["source"] == "market_data_keyword"
        assert result["suggested_price"] is not None

    def test_gemini_fallback(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=[]), \
             patch.object(engine, "get_ai_price_estimate", return_value={"price": 50.0, "reasoning": "AI est"}):
            result = engine.get_price_with_comps("Rare Gadget")
        assert result["source"] == "ai_grounded_research"
        # 50.0 -> smart pricing: floor(50)-0.01 = 49.99
        assert result["suggested_price"] == 49.99

    def test_gemini_with_shipping_buffer(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=[]), \
             patch.object(engine, "get_ai_price_estimate", return_value={"price": 50.0, "reasoning": "AI est"}):
            result = engine.get_price_with_comps("Rare Gadget", shipping_cost=6.50)
        # 50 + 6.50 = 56.50 -> smart pricing: floor=56, cents=0.50 < 0.80 -> 55.99
        assert result["suggested_price"] == 55.99

    def test_ai_estimate_fallback(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=[]), \
             patch.object(engine, "get_ai_price_estimate", return_value=None):
            result = engine.get_price_with_comps("Unknown Widget", ai_suggested_price="30")
        assert result["source"] == "ai_estimate"
        # 30.0 -> smart pricing: floor(30)-0.01 = 29.99
        assert result["suggested_price"] == 29.99

    def test_all_fail(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=[]), \
             patch.object(engine, "get_ai_price_estimate", return_value=None):
            result = engine.get_price_with_comps("Unknown Widget")
        assert result["source"] == "failed_requires_manual"
        assert result["suggested_price"] is None

    def test_research_link_always_present(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=[]), \
             patch.object(engine, "get_ai_price_estimate", return_value=None):
            result = engine.get_price_with_comps("Anything At All")
        assert "research_link" in result
        assert "ebay.com" in result["research_link"]

    def test_condition_passed_to_browse_api(self, engine):
        """Condition should be passed through to search_sold_listings."""
        with patch.object(engine, "search_sold_listings", return_value=self._sold) as mock_search:
            engine.get_price_with_comps("Test Item", condition="USED_GOOD")
        # Verify condition was passed through
        call_kwargs = mock_search.call_args
        assert call_kwargs[1].get("condition") == "USED_GOOD" or \
               (len(call_kwargs[0]) >= 4 and call_kwargs[0][3] == "USED_GOOD")


# ---------------------------------------------------------------------------
# TestGenerateSearchLink
# ---------------------------------------------------------------------------


class TestGenerateSearchLink:
    def test_basic_link(self, engine):
        url = engine.generate_ebay_search_link("Hello World Test")
        assert "ebay.com" in url
        assert "LH_Sold=1" in url
        assert "Hello" in url

    def test_uses_first_6_words(self, engine):
        title = "One Two Three Four Five Six Seven Eight Nine Ten"
        url = engine.generate_ebay_search_link(title)
        assert "Seven" not in url
        assert "Six" in url


# ---------------------------------------------------------------------------
# TestSmartPricingRounding
# ---------------------------------------------------------------------------


class TestSmartPricingRounding:
    """Smart pricing rounds to nearest .99 without aggressive inflation.

    Rules (prices > $15 only):
    - cents >= 0.80: round UP to current dollar .99 ($44.85 -> $44.99)
    - cents < 0.80: round DOWN to previous dollar .99 ($44.32 -> $43.99)
    - exact whole numbers (0.00 cents): round DOWN ($45.00 -> $44.99)
    """

    def test_price_below_80_cents_rounds_down(self, engine):
        """$44.32 -> floor is $44, cents=0.32 < 0.80, so $43.99"""
        items = _make_sold_items([44.32])
        result = engine.calculate_suggested_price(items, our_condition="New")
        assert result["suggested_price"] == 43.99

    def test_price_above_80_cents_rounds_up(self, engine):
        """$44.85 -> floor is $44, cents=0.85 >= 0.80, so $44.99"""
        items = _make_sold_items([44.85])
        result = engine.calculate_suggested_price(items, our_condition="New")
        assert result["suggested_price"] == 44.99

    def test_price_at_whole_number_stays_99(self, engine):
        """$45.00 -> floor is $45, cents=0.00 < 0.80, so $44.99"""
        items = _make_sold_items([45.00])
        result = engine.calculate_suggested_price(items, our_condition="New")
        assert result["suggested_price"] == 44.99

    def test_price_just_above_whole_rounds_down(self, engine):
        """$45.01 -> floor is $45, cents=0.01 < 0.80, so $44.99"""
        items = _make_sold_items([45.01])
        result = engine.calculate_suggested_price(items, our_condition="New")
        assert result["suggested_price"] == 44.99

    def test_price_under_15_no_rounding(self, engine):
        """Prices <= $15 should NOT be smart-rounded"""
        items = _make_sold_items([8.50])
        result = engine.calculate_suggested_price(items, our_condition="New")
        assert result["suggested_price"] == 8.50


# ---------------------------------------------------------------------------
# TestShippingBufferConsistency
# ---------------------------------------------------------------------------


class TestShippingBufferConsistency:
    """Shipping buffer must be added exactly once across all pricing paths."""

    @patch.object(PricingEngine, 'search_sold_listings', return_value=[])
    @patch.object(PricingEngine, 'get_ai_price_estimate')
    def test_ai_grounding_adds_shipping_once(self, mock_ai_est, mock_search, engine):
        """AI grounding returns base price; shipping added by get_price_with_comps, not the prompt."""
        mock_ai_est.return_value = {"price": 50.00, "reasoning": "Based on research"}
        result = engine.get_price_with_comps("Test Item", condition="USED_GOOD", shipping_cost=6.50)
        # AI returns 50, shipping 6.50 added once = 56.50
        # smart pricing: floor=56, cents=0.50 < 0.80 -> 55.99
        assert result["suggested_price"] == 55.99
        assert result["source"] == "ai_grounded_research"

    @patch.object(PricingEngine, 'search_sold_listings', return_value=[])
    @patch.object(PricingEngine, 'get_ai_price_estimate', return_value=None)
    def test_ai_fallback_adds_shipping_once(self, mock_ai_est, mock_search, engine):
        """AI image estimate fallback also adds shipping exactly once."""
        result = engine.get_price_with_comps("Test Item", condition="USED_GOOD", ai_suggested_price="40.00", shipping_cost=6.50)
        # ai_suggested_price=40, shipping 6.50 added once = 46.50
        # smart pricing: floor=46, cents=0.50 < 0.80 -> 45.99
        assert result["suggested_price"] == 45.99
        assert result["source"] == "ai_estimate"


# ---------------------------------------------------------------------------
# TestSmartQueryConstruction
# ---------------------------------------------------------------------------

class TestSmartQueryConstruction:
    """Search queries should prioritize identifiers over raw title words."""

    def test_build_search_query_uses_brand_mpn(self):
        engine = PricingEngine.__new__(PricingEngine)
        query = engine._build_keyword_query(
            title="Genuine Xerox 108R00713 Solid Ink Cyan for Phaser 8560 OEM New",
            identification={"brand": "Xerox", "mpn": "108R00713", "model": "Phaser 8560"}
        )
        assert "Xerox" in query
        assert "108R00713" in query

    def test_build_search_query_fallback_to_title(self):
        engine = PricingEngine.__new__(PricingEngine)
        query = engine._build_keyword_query(
            title="Vintage Brass Compass Navigation Tool Antique Maritime",
            identification=None
        )
        assert "Vintage" in query
        assert len(query.split()) <= 8

    def test_build_search_query_no_duplicate_brand(self):
        """If brand is already in the title fragment, don't double it."""
        engine = PricingEngine.__new__(PricingEngine)
        query = engine._build_keyword_query(
            title="Xerox 108R00713 Solid Ink",
            identification={"brand": "Xerox", "mpn": "108R00713", "model": ""}
        )
        assert query.count("Xerox") == 1


# ---------------------------------------------------------------------------
# TestCompFiltering
# ---------------------------------------------------------------------------


class TestCompFiltering:
    """Comps should be filtered for relevance before price calculation."""

    def test_title_similarity_filters_irrelevant_comps(self, engine):
        """Comps with low title similarity should be excluded."""
        comps = [
            {"title": "Aiwa CSD-ES227 Boombox CD Cassette", "price": 50.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Aiwa CSD-ES227 Boombox Stereo", "price": 55.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Aiwa CSD-ES227 CD Player Portable", "price": 48.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Tesla Model 3 Floor Mat Set", "price": 200.0, "condition": "New", "end_date": "", "url": ""},
            {"title": "iPhone 15 Pro Case Cover", "price": 5.0, "condition": "New", "end_date": "", "url": ""},
        ]
        filtered = engine.filter_comps(comps, reference_title="Aiwa CSD-ES227 Boombox CD Cassette Player")
        assert len(filtered) == 3
        assert all("Aiwa" in c["title"] for c in filtered)

    def test_outlier_rejection_removes_extremes(self, engine):
        """Prices >2 std devs from median should be dropped."""
        comps = _make_sold_items([50, 52, 48, 55, 51, 300])  # 300 is an outlier
        filtered = engine.filter_comps(comps, reference_title="Generic Item")
        prices = [c["price"] for c in filtered]
        assert 300 not in prices

    def test_filter_preserves_minimum_comps(self, engine):
        """Even with aggressive filtering, keep at least 3 comps if available."""
        comps = [
            {"title": "Widget A", "price": 10.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Widget B", "price": 12.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Widget C", "price": 11.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Totally Different Thing", "price": 50.0, "condition": "New", "end_date": "", "url": ""},
        ]
        filtered = engine.filter_comps(comps, reference_title="Widget A Model X")
        assert len(filtered) >= 3

    def test_empty_comps_returns_empty(self, engine):
        filtered = engine.filter_comps([], reference_title="Anything")
        assert filtered == []


# ---------------------------------------------------------------------------
# TestPriceSourceLabeling
# ---------------------------------------------------------------------------

class TestPriceSourceLabeling:
    """Price source labels should be human-readable."""

    def test_isbn_source_labeled_correctly(self):
        from backend.app.services.pricing_engine import format_price_source
        label = format_price_source('market_data_isbn', comp_count=8)
        assert 'ISBN' in label
        assert '8' in label

    def test_keyword_source_labeled(self):
        from backend.app.services.pricing_engine import format_price_source
        label = format_price_source('market_data_keyword', comp_count=5)
        assert 'listings' in label.lower()
        assert '5' in label

    def test_ai_source_labeled(self):
        from backend.app.services.pricing_engine import format_price_source
        label = format_price_source('ai_grounding')
        assert 'AI' in label

    def test_unknown_source_returns_raw(self):
        from backend.app.services.pricing_engine import format_price_source
        assert format_price_source('something_custom') == 'something_custom'


class TestSameGradeComps:
    """Within the eBay USED bucket, prefer comps matching our exact grade."""

    def _comps(self):
        return [
            {"title": "A", "price": 199.99, "condition": "Pre-owned - Excellent"},
            {"title": "B", "price": 200.00, "condition": "Pre-owned - Excellent"},
            {"title": "C", "price": 185.00, "condition": "Used - Excellent"},
            {"title": "D", "price": 190.00, "condition": "Pre-owned - Excellent"},
            {"title": "E", "price": 80.00, "condition": "Pre-owned - Good"},
            {"title": "F", "price": 74.99, "condition": "Pre-owned - Good"},
        ]

    def test_filters_to_matching_grade_when_enough(self):
        from backend.app.services.pricing_engine import PricingEngine
        subset, filtered = PricingEngine.prefer_same_grade_comps(self._comps(), "USED_EXCELLENT")
        assert filtered is True
        assert len(subset) == 4
        assert all("Excellent" in c["condition"] for c in subset)

    def test_keeps_all_when_too_few_match(self):
        from backend.app.services.pricing_engine import PricingEngine
        subset, filtered = PricingEngine.prefer_same_grade_comps(self._comps(), "USED_GOOD")
        assert filtered is False
        assert len(subset) == 6

    def test_unknown_condition_keeps_all(self):
        from backend.app.services.pricing_engine import PricingEngine
        subset, filtered = PricingEngine.prefer_same_grade_comps(self._comps(), None)
        assert filtered is False
        assert len(subset) == 6

    def test_very_good_not_confused_with_good(self):
        from backend.app.services.pricing_engine import PricingEngine
        comps = [
            {"title": "A", "price": 50, "condition": "Pre-owned - Very Good"},
            {"title": "B", "price": 52, "condition": "Pre-owned - Very Good"},
            {"title": "C", "price": 55, "condition": "Pre-owned - Very Good"},
            {"title": "D", "price": 51, "condition": "Pre-owned - Very Good"},
            {"title": "E", "price": 20, "condition": "Pre-owned - Good"},
        ]
        subset, filtered = PricingEngine.prefer_same_grade_comps(comps, "USED_VERY_GOOD")
        assert filtered is True
        assert len(subset) == 4

    def test_median_uses_same_grade_subset(self):
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine()
        result = engine.calculate_suggested_price(self._comps(), our_condition="USED_EXCELLENT")
        # Median of the 4 Excellent comps (185, 190, 199.99, 200) = 194.995,
        # NOT the all-6 median dragged down by the Good pairs
        assert result["median_price"] > 150
        assert "same-grade" in result["reasoning"]
