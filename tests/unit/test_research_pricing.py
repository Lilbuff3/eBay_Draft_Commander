"""Tests for Phase 2 research market price passthrough to pricing engine."""
import pytest
from unittest.mock import MagicMock, patch


class TestResearchPricePassthrough:
    """Verify research_market_price flows from processor -> agent -> pricing engine."""

    def test_research_price_passed_to_pricing(self):
        """When research has market_price, it should be passed to pricing engine."""
        from backend.app.services.listing_ai_agent import ListingAIAgent

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent._default_shipping_cost = 6.50

        mock_engine = MagicMock()
        mock_engine.get_price_with_comps.return_value = {
            "suggested_price": 49.99,
            "comps": [],
            "reasoning": "test",
            "source": "research_market_price",
            "research_link": ""
        }
        agent.pricing_engine = mock_engine

        research_mp = {"low": 30, "mid": 50, "high": 80}
        agent.get_final_pricing(
            "Test Item",
            "Used - Good",
            "45.00",
            None,
            shipping_cost=6.50,
            research_market_price=research_mp,
        )

        mock_engine.get_price_with_comps.assert_called_once()
        call_kwargs = mock_engine.get_price_with_comps.call_args[1]
        assert call_kwargs.get("research_market_price") == research_mp

    def test_research_price_not_passed_when_none(self):
        """When no research market price, kwarg should be None."""
        from backend.app.services.listing_ai_agent import ListingAIAgent

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent._default_shipping_cost = 6.50

        mock_engine = MagicMock()
        mock_engine.get_price_with_comps.return_value = {
            "suggested_price": 29.99,
            "comps": [],
            "reasoning": "test",
            "source": "ai_estimate",
            "research_link": ""
        }
        agent.pricing_engine = mock_engine

        agent.get_final_pricing(
            "Test Item",
            "Used - Good",
            "30.00",
            None,
            shipping_cost=6.50,
        )

        call_kwargs = mock_engine.get_price_with_comps.call_args[1]
        assert call_kwargs.get("research_market_price") is None


class TestResearchPriceStrategy:
    """Verify Strategy 2.5 in pricing engine uses research price before Gemini grounding."""

    def _make_engine(self):
        """Create a PricingEngine with mocked external dependencies."""
        from backend.app.services.pricing_engine import PricingEngine

        engine = PricingEngine.__new__(PricingEngine)
        engine.app_id = "test"
        engine.google_api_key = None
        engine.ai_client = None
        return engine

    def test_research_price_used_before_gemini_grounding(self):
        """Research price should short-circuit Strategy 3 (Gemini grounding)."""
        engine = self._make_engine()

        # Mock all earlier strategies to return nothing
        engine.search_finding_api = MagicMock(return_value=[])
        engine.search_sold_listings = MagicMock(return_value=[])
        engine.generate_ebay_search_link = MagicMock(return_value="https://ebay.com/test")
        engine.get_ai_price_estimate = MagicMock(return_value={"price": 999.99})

        result = engine.get_price_with_comps(
            "Vintage Widget",
            condition="Used - Good",
            research_market_price={"low": 40, "mid": 75, "high": 120},
            shipping_cost=6.50,
        )

        assert result["source"] == "research_market_price"
        # Gemini grounding should NOT have been called
        engine.get_ai_price_estimate.assert_not_called()
        # Price should reflect condition multiplier (0.75) + shipping
        # 75 * 0.75 = 56.25 + 6.50 = 62.75 -> smart_round_99 (cents 0.75 < 0.80) -> 61.99
        assert result["suggested_price"] == 61.99

    def test_research_price_applies_condition_multiplier(self):
        """Different conditions should produce different prices from same mid."""
        engine = self._make_engine()

        engine.search_finding_api = MagicMock(return_value=[])
        engine.search_sold_listings = MagicMock(return_value=[])
        engine.generate_ebay_search_link = MagicMock(return_value="")
        engine.get_ai_price_estimate = MagicMock(return_value=None)

        # Like New should be higher than Used Good
        result_ln = engine.get_price_with_comps(
            "Widget",
            condition="Used - Like New",
            research_market_price={"low": 40, "mid": 100, "high": 150},
            shipping_cost=0,
        )
        result_ug = engine.get_price_with_comps(
            "Widget",
            condition="Used - Good",
            research_market_price={"low": 40, "mid": 100, "high": 150},
            shipping_cost=0,
        )

        assert result_ln["suggested_price"] > result_ug["suggested_price"]

    def test_research_price_skipped_when_no_mid(self):
        """If research_market_price has no 'mid', skip to next strategy."""
        engine = self._make_engine()

        engine.search_finding_api = MagicMock(return_value=[])
        engine.search_sold_listings = MagicMock(return_value=[])
        engine.generate_ebay_search_link = MagicMock(return_value="")
        engine.get_ai_price_estimate = MagicMock(return_value={"price": 50.0, "reasoning": "AI"})

        result = engine.get_price_with_comps(
            "Widget",
            condition="Used - Good",
            research_market_price={"low": 40, "high": 120},  # no mid
            shipping_cost=0,
            ai_suggested_price="30.00",
        )

        # Should fall through to Gemini grounding (Strategy 3)
        assert result["source"] == "ai_grounded_research"

    def test_research_price_skipped_when_none(self):
        """If research_market_price is None, skip to next strategy."""
        engine = self._make_engine()

        engine.search_finding_api = MagicMock(return_value=[])
        engine.search_sold_listings = MagicMock(return_value=[])
        engine.generate_ebay_search_link = MagicMock(return_value="")
        engine.get_ai_price_estimate = MagicMock(return_value={"price": 50.0, "reasoning": "AI"})

        result = engine.get_price_with_comps(
            "Widget",
            condition="Used - Good",
            research_market_price=None,
            shipping_cost=0,
            ai_suggested_price="30.00",
        )

        assert result["source"] == "ai_grounded_research"

    def test_research_price_invalid_mid_falls_through(self):
        """If mid value can't be converted to float, skip gracefully."""
        engine = self._make_engine()

        engine.search_finding_api = MagicMock(return_value=[])
        engine.search_sold_listings = MagicMock(return_value=[])
        engine.generate_ebay_search_link = MagicMock(return_value="")
        engine.get_ai_price_estimate = MagicMock(return_value=None)

        result = engine.get_price_with_comps(
            "Widget",
            condition="Used - Good",
            research_market_price={"low": 40, "mid": "not_a_number", "high": 120},
            shipping_cost=0,
            ai_suggested_price="25.00",
        )

        # Should fall through past Strategy 2.5 to AI estimate (Strategy 4)
        assert result["source"] == "ai_estimate"


class TestPricingCompsPassthrough:
    """Verify get_final_pricing returns comps, reasoning, and source from pricing engine."""

    def _make_agent(self):
        from backend.app.services.listing_ai_agent import ListingAIAgent

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent._default_shipping_cost = 6.50
        return agent

    def test_comps_returned_from_get_final_pricing(self):
        """get_final_pricing should return comps from pricing engine."""
        agent = self._make_agent()

        sample_comps = [
            {"title": "Similar Widget", "price": 45.00, "condition": "Used"},
            {"title": "Another Widget", "price": 52.00, "condition": "Used"},
        ]
        mock_engine = MagicMock()
        mock_engine.get_price_with_comps.return_value = {
            "suggested_price": 49.99,
            "comps": sample_comps,
            "reasoning": "Based on 2 comparable sales",
            "source": "finding_api_sold",
            "research_link": "",
        }
        agent.pricing_engine = mock_engine

        result = agent.get_final_pricing(
            "Test Widget",
            "Used - Good",
            "45.00",
            None,
            shipping_cost=6.50,
        )

        assert result["comps"] == sample_comps
        assert result["reasoning"] == "Based on 2 comparable sales"
        assert result["source"] == "finding_api_sold"
        assert result["price"] == "49.99"

    def test_comps_empty_on_error(self):
        """When pricing fails, comps should be empty list."""
        agent = self._make_agent()

        mock_engine = MagicMock()
        mock_engine.get_price_with_comps.side_effect = RuntimeError("API timeout")
        agent.pricing_engine = mock_engine

        result = agent.get_final_pricing(
            "Test Widget",
            "Used - Good",
            "45.00",
            None,
            shipping_cost=6.50,
        )

        assert result["comps"] == []
        assert result["reasoning"] == ""
        assert result["source"] == ""
        assert result["price"] == "0.00"
        assert "warning" in result


class TestAvailabilityPricing:
    """Verify rare/very_rare items use 75th percentile pricing."""

    def _make_engine(self):
        from backend.app.services.pricing_engine import PricingEngine

        engine = PricingEngine.__new__(PricingEngine)
        engine.app_id = "test"
        engine.google_api_key = None
        engine.ai_client = None
        return engine

    def _make_sold_items(self, prices):
        """Create minimal sold_items list from a list of prices."""
        return [{"price": p, "condition": "Used - Good"} for p in prices]

    def test_rare_item_prices_higher_than_common(self):
        """Rare items should use 75th percentile, pricing higher than median."""
        engine = self._make_engine()
        prices = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        sold_items = self._make_sold_items(prices)

        result_common = engine.calculate_suggested_price(
            sold_items, "Used - Good", shipping_cost=0, availability="common"
        )
        result_rare = engine.calculate_suggested_price(
            sold_items, "Used - Good", shipping_cost=0, availability="rare"
        )

        assert result_rare["suggested_price"] > result_common["suggested_price"]

    def test_very_rare_also_uses_75th_percentile(self):
        """very_rare should behave the same as rare (75th percentile)."""
        engine = self._make_engine()
        prices = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        sold_items = self._make_sold_items(prices)

        result_rare = engine.calculate_suggested_price(
            sold_items, "Used - Good", shipping_cost=0, availability="rare"
        )
        result_very_rare = engine.calculate_suggested_price(
            sold_items, "Used - Good", shipping_cost=0, availability="very_rare"
        )

        assert result_very_rare["suggested_price"] == result_rare["suggested_price"]

    def test_common_item_uses_median(self):
        """Common/moderate items should use normal median pricing."""
        engine = self._make_engine()
        prices = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        sold_items = self._make_sold_items(prices)

        result_common = engine.calculate_suggested_price(
            sold_items, "Used - Good", shipping_cost=0, availability="common"
        )
        result_moderate = engine.calculate_suggested_price(
            sold_items, "Used - Good", shipping_cost=0, availability="moderate"
        )

        # Both should produce the same price (median-based)
        assert result_common["suggested_price"] == result_moderate["suggested_price"]

    def test_availability_none_uses_median(self):
        """When availability is None, default to median."""
        engine = self._make_engine()
        prices = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        sold_items = self._make_sold_items(prices)

        result_none = engine.calculate_suggested_price(
            sold_items, "Used - Good", shipping_cost=0, availability=None
        )
        result_common = engine.calculate_suggested_price(
            sold_items, "Used - Good", shipping_cost=0, availability="common"
        )

        assert result_none["suggested_price"] == result_common["suggested_price"]

    def test_rare_reasoning_mentions_percentile(self):
        """Reasoning string should indicate 75th percentile for rare items."""
        engine = self._make_engine()
        sold_items = self._make_sold_items([20, 40, 60, 80])

        result = engine.calculate_suggested_price(
            sold_items, "Used - Good", shipping_cost=0, availability="rare"
        )

        assert "75th pctl" in result["reasoning"]

    def test_common_reasoning_mentions_median(self):
        """Reasoning string should say Median for common items."""
        engine = self._make_engine()
        sold_items = self._make_sold_items([20, 40, 60, 80])

        result = engine.calculate_suggested_price(
            sold_items, "Used - Good", shipping_cost=0, availability="common"
        )

        assert "Median" in result["reasoning"]

    def test_availability_threaded_through_get_price_with_comps(self):
        """availability should be passed from get_price_with_comps to calculate_suggested_price."""
        engine = self._make_engine()

        engine.search_finding_api = MagicMock(return_value=[])
        engine.search_sold_listings = MagicMock(return_value=[])
        engine.generate_ebay_search_link = MagicMock(return_value="")
        engine.get_ai_price_estimate = MagicMock(return_value=None)

        # Mock calculate_suggested_price to capture the call
        engine.calculate_suggested_price = MagicMock(return_value={
            "suggested_price": 50.0,
            "comp_count": 3,
            "median_price": 45.0,
            "reasoning": "test",
        })

        # Provide sold items via Finding API so calculate_suggested_price gets called
        engine.search_finding_api = MagicMock(return_value=[
            {"title": "Test", "price": 50.0, "condition": "Used", "end_date": "", "url": ""}
        ])

        engine.get_price_with_comps(
            "Test Item", condition="Used - Good", availability="very_rare"
        )

        call_kwargs = engine.calculate_suggested_price.call_args
        assert call_kwargs[1].get("availability") == "very_rare"

    def test_availability_threaded_through_agent(self):
        """availability should pass from ListingAIAgent to pricing engine."""
        from backend.app.services.listing_ai_agent import ListingAIAgent

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent._default_shipping_cost = 6.50

        mock_engine = MagicMock()
        mock_engine.get_price_with_comps.return_value = {
            "suggested_price": 79.99,
            "comps": [],
            "reasoning": "test",
            "source": "market_data_sold",
            "research_link": "",
        }
        agent.pricing_engine = mock_engine

        agent.get_final_pricing(
            "Rare Widget",
            "Used - Good",
            "50.00",
            None,
            shipping_cost=6.50,
            availability="rare",
        )

        call_kwargs = mock_engine.get_price_with_comps.call_args[1]
        assert call_kwargs.get("availability") == "rare"


class TestResearchSpecsInPrompt:
    """Verify web-verified specs are passed to the aspect enrichment prompt."""

    def test_research_specs_included_in_prompt(self):
        """When research_specs provided, they appear in the prompt."""
        from backend.app.core.prompts import ASPECT_ENRICHMENT_PROMPT

        research_specs = {"Voltage": "120V", "Interface": "USB 3.0"}
        specs_lines = [f"- {k}: {v}" for k, v in research_specs.items() if v]
        research_specs_section = (
            "WEB-VERIFIED SPECIFICATIONS (use these as ground truth, "
            "more reliable than guessing):\n" + "\n".join(specs_lines)
        )

        prompt = ASPECT_ENRICHMENT_PROMPT.format(
            title="Test Widget",
            brand="Acme",
            model="X100",
            mpn="ACM-X100",
            category_name="Widgets",
            research_specs_section=research_specs_section,
            aspect_list="- [REQUIRED] Brand: (free text)",
            existing_specifics="(none filled yet)",
        )

        assert "WEB-VERIFIED SPECIFICATIONS" in prompt
        assert "- Voltage: 120V" in prompt
        assert "- Interface: USB 3.0" in prompt

    def test_no_research_specs_no_section(self):
        """When research_specs is None, no section in prompt."""
        from backend.app.core.prompts import ASPECT_ENRICHMENT_PROMPT

        prompt = ASPECT_ENRICHMENT_PROMPT.format(
            title="Test Widget",
            brand="Acme",
            model="X100",
            mpn="ACM-X100",
            category_name="Widgets",
            research_specs_section="",
            aspect_list="- [REQUIRED] Brand: (free text)",
            existing_specifics="(none filled yet)",
        )

        assert "WEB-VERIFIED SPECIFICATIONS" not in prompt
        # Prompt should still be valid
        assert "Title: Test Widget" in prompt
        assert "Brand: Acme" in prompt

    def test_enrich_builds_specs_section_correctly(self):
        """enrich_item_specifics should build the specs section from research_specs dict."""
        from backend.app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        analyzer.client = None  # Will cause early return

        result = analyzer.enrich_item_specifics(
            image_paths=[],
            title="Test",
            identification={},
            category_name="Test",
            aspect_schema=[],  # Empty schema triggers early return
            existing_specifics={"Brand": "Acme"},
            research_specs={"Voltage": "120V"},
        )

        # With no client or empty schema, should return existing_specifics unchanged
        assert result == {"Brand": "Acme"}

    def test_research_specs_with_empty_values_filtered(self):
        """Empty/falsy spec values should be filtered out."""
        research_specs = {"Voltage": "120V", "Interface": "", "Color": None, "Size": "Large"}
        specs_lines = [f"- {k}: {v}" for k, v in research_specs.items() if v]
        research_specs_section = (
            "WEB-VERIFIED SPECIFICATIONS (use these as ground truth, "
            "more reliable than guessing):\n" + "\n".join(specs_lines)
        )

        assert "- Voltage: 120V" in research_specs_section
        assert "- Size: Large" in research_specs_section
        assert "Interface" not in research_specs_section
        assert "Color" not in research_specs_section
