"""
Tests for PricingEngine — condition multipliers, price calculation, comp strategies.
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
# TestConditionMultipliers
# ---------------------------------------------------------------------------


class TestConditionMultipliers:
    def test_all_nine_exist(self):
        assert len(PricingEngine.CONDITION_MULTIPLIERS) == 9

    def test_new_is_1_0(self):
        assert PricingEngine.CONDITION_MULTIPLIERS["New"] == 1.0

    def test_used_good_is_0_75(self):
        assert PricingEngine.CONDITION_MULTIPLIERS["Used - Good"] == 0.75

    def test_for_parts_is_0_40(self):
        assert PricingEngine.CONDITION_MULTIPLIERS["For Parts"] == 0.40

    def test_nos_is_0_95(self):
        assert PricingEngine.CONDITION_MULTIPLIERS["New Old Stock"] == 0.95


# ---------------------------------------------------------------------------
# TestCalculateSuggestedPrice
# ---------------------------------------------------------------------------


class TestCalculateSuggestedPrice:
    def test_median_calculation(self, engine):
        items = _make_sold_items([10, 20, 30, 40, 50])
        result = engine.calculate_suggested_price(items, our_condition="New")
        # median=30, multiplier=1.0, price=30 -> >10 smart pricing -> round(30)-0.01=29.99
        assert result["median_price"] == 30.0
        assert result["suggested_price"] == 29.99

    def test_condition_multiplier_applied(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="Used - Good")
        # median=100, multiplier=0.75 -> 75 -> smart pricing -> round(75)-0.01=74.99
        assert result["multiplier"] == 0.75
        assert result["suggested_price"] == 74.99

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
        # median=40, multiplier=1.0 -> 40 + 6.50 = 46.50
        # smart pricing: round(46.50) = 46 (banker's rounding) -> 46 - 0.01 = 45.99
        assert result["suggested_price"] == 45.99
        assert "shipping" in result["reasoning"]

    def test_smart_99_above_10(self, engine):
        items = _make_sold_items([45])
        result = engine.calculate_suggested_price(items, our_condition="New")
        # median=45, multiplier=1.0 -> 45.0 -> >10 -> round(45)-0.01 = 44.99
        assert result["suggested_price"] == 44.99

    def test_no_smart_pricing_at_or_below_10(self, engine):
        items = _make_sold_items([10])
        result = engine.calculate_suggested_price(items, our_condition="New")
        # median=10, multiplier=1.0 -> 10.0 -> NOT > 10 -> stays 10.0
        assert result["suggested_price"] == 10.0

    def test_margin_boost_triggered(self, engine):
        items = _make_sold_items([40])
        result = engine.calculate_suggested_price(
            items, our_condition="Used - Good", acquisition_cost=50, shipping_cost=6.50
        )
        # median=40, multiplier=0.75 -> 30 + 6.50 = 36.50
        # est_fees = 36.50*0.1325 + 0.30 = 5.14 + 0.30 = 5.44
        # projected_profit = 36.50 - 5.44 - 50 - 6.50 = -25.44 (< 10)
        # target_price = (50 + 10 + 0.30) / (1 - 0.1325) = 60.30 / 0.8675 = 69.51...
        # margin_boost=True -> smart pricing round(69.51)-0.01 = 69.99
        assert result["suggested_price"] == 69.99
        assert "Boosted" in result["reasoning"]

    def test_no_margin_boost_zero_acquisition(self, engine):
        items = _make_sold_items([10])
        result = engine.calculate_suggested_price(items, our_condition="Used - Good")
        # acquisition_cost=0 (default) -> no boost, even though profit is tiny
        assert "Boosted" not in result["reasoning"]

    def test_nos_fuzzy_matching_full(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="New Old Stock")
        assert result["multiplier"] == 0.95

    def test_nos_fuzzy_matching_short(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="NOS")
        # "nos" in "NOS".lower() -> cond_key = "New Old Stock" -> 0.95
        assert result["multiplier"] == 0.95

    def test_unknown_condition_defaults(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="Random Junk")
        # Not in CONDITION_MULTIPLIERS, default fallback is 0.75
        assert result["multiplier"] == 0.75


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
        assert result["source"] == "market_data"

    def test_keyword_search_succeeds(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=self._sold):
            result = engine.get_price_with_comps("Test Item Title")
        assert result["source"] == "market_data"
        assert result["suggested_price"] is not None

    def test_gemini_fallback(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=[]), \
             patch.object(engine, "get_ai_price_estimate", return_value={"price": 50.0, "reasoning": "AI est"}):
            result = engine.get_price_with_comps("Rare Gadget")
        assert result["source"] == "ai_grounded_research"
        assert result["suggested_price"] == 50.0

    def test_gemini_with_shipping_buffer(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=[]), \
             patch.object(engine, "get_ai_price_estimate", return_value={"price": 50.0, "reasoning": "AI est"}):
            result = engine.get_price_with_comps("Rare Gadget", shipping_cost=6.50)
        assert result["suggested_price"] == 56.50

    def test_ai_estimate_fallback(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=[]), \
             patch.object(engine, "get_ai_price_estimate", return_value=None):
            result = engine.get_price_with_comps("Unknown Widget", ai_suggested_price="30")
        assert result["source"] == "ai_estimate"
        assert result["suggested_price"] == 30.0

    def test_all_fail(self, engine):
        with patch.object(engine, "search_sold_listings", return_value=[]), \
             patch.object(engine, "get_ai_price_estimate", return_value=None):
            result = engine.get_price_with_comps("Unknown Widget")
        assert result["source"] == "failed_requires_manual"
        assert result["suggested_price"] is None

    def test_research_link_always_present(self, engine):
        # Every code path should return a research_link
        with patch.object(engine, "search_sold_listings", return_value=[]), \
             patch.object(engine, "get_ai_price_estimate", return_value=None):
            result = engine.get_price_with_comps("Anything At All")
        assert "research_link" in result
        assert "ebay.com" in result["research_link"]


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
