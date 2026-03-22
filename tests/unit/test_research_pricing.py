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
