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
        # smart pricing: floor(46.50)=46, cents=0.50 < 0.80 -> 46-0.01 = 45.99
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
        # margin_boost=True -> smart pricing: floor(69.51)=69, cents=0.51 < 0.80 -> 68.99
        assert result["suggested_price"] == 68.99
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
        # 50.0 -> smart pricing ceil(50) - 0.01 = 49.99
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
        # 30.0 -> smart pricing ceil(30) - 0.01 = 29.99
        assert result["suggested_price"] == 29.99

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


class TestConditionEnumLookup:
    """Verify pricing engine handles ENUM-style condition keys from the pipeline."""

    def test_used_excellent_enum_gets_correct_multiplier(self, engine):
        """Pipeline passes 'USED_EXCELLENT' — must NOT fall to 0.75 default."""
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="USED_EXCELLENT")
        assert result["multiplier"] == 0.85, f"USED_EXCELLENT should be 0.85, got {result['multiplier']}"

    def test_new_other_enum_gets_correct_multiplier(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="NEW_OTHER")
        assert result["multiplier"] == 0.90

    def test_used_good_enum_gets_correct_multiplier(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="USED_GOOD")
        assert result["multiplier"] == 0.75

    def test_for_parts_enum_gets_correct_multiplier(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="FOR_PARTS_OR_NOT_WORKING")
        assert result["multiplier"] == 0.40

    def test_new_enum_gets_correct_multiplier(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="NEW")
        assert result["multiplier"] == 1.0

    def test_like_new_enum_gets_correct_multiplier(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="LIKE_NEW")
        assert result["multiplier"] == 0.85

    def test_display_format_still_works(self, engine):
        """Backward compat: display-style keys must still resolve."""
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="Used - Good")
        assert result["multiplier"] == 0.75

    def test_used_very_good_enum_gets_correct_multiplier(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="USED_VERY_GOOD")
        assert result["multiplier"] == 0.85

    def test_used_acceptable_enum_gets_correct_multiplier(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="USED_ACCEPTABLE")
        assert result["multiplier"] == 0.60

    def test_seller_refurbished_enum_gets_correct_multiplier(self, engine):
        items = _make_sold_items([100])
        result = engine.calculate_suggested_price(items, our_condition="SELLER_REFURBISHED")
        assert result["multiplier"] == 0.85


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

    Rules (prices > $10 only):
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

    def test_price_under_10_no_rounding(self, engine):
        """Prices <= $10 should NOT be smart-rounded"""
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
