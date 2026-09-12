"""Unit tests for COGS tracking, Net Margin calculations, and Profit Floor enforcement."""
import pytest
from unittest.mock import MagicMock
from backend.app.services.ledger import estimate_net
from backend.app.services.pricing_engine import PricingEngine
from backend.app.core.constants import EBAY_FINAL_VALUE_FEE_RATE, EBAY_PAYMENT_PROCESSING_FEE


class TestLedgerEstimateNet:
    def test_estimate_net_without_cogs_returns_none_net(self):
        res = estimate_net(100.0, cogs=None, ship_cost=5.0)
        assert res['fees_est'] == round(100.0 * EBAY_FINAL_VALUE_FEE_RATE + EBAY_PAYMENT_PROCESSING_FEE, 2)
        assert res['ship_est'] == 5.0
        assert res['net'] is None

    def test_estimate_net_with_cogs_calculates_correct_profit(self):
        # 100 - (13.25 + 0.30) - 5.0 - 20.0 = 61.45
        res = estimate_net(100.0, cogs=20.0, ship_cost=5.0)
        assert res['net'] == 61.45


class TestPricingEngineMarginFloor:
    def test_suggested_price_boosted_when_cogs_threatens_min_margin(self):
        engine = PricingEngine()
        # Item comps suggest 30, but COGS is 25, min margin is 10
        # Boosted target price = (25 + 10 + 0.30) / (1 - 0.1325) = 35.30 / 0.8675 = 40.69 -> 40.99
        sold_items = [{'price': '30.00', 'condition': 'Used'}]
        res = engine.calculate_suggested_price(
            sold_items=sold_items,
            our_condition="Used - Good",
            acquisition_cost=25.0,
            shipping_cost=0.0
        )
        assert res['suggested_price'] > 30.0
        assert res['projected_profit'] >= 10.0
        assert "(Boosted for $10.0 min margin)" in res['reasoning']

    def test_suggested_price_not_boosted_when_margin_is_healthy(self):
        engine = PricingEngine()
        sold_items = [{'price': '50.00', 'condition': 'Used'}]
        res = engine.calculate_suggested_price(
            sold_items=sold_items,
            our_condition="Used - Good",
            acquisition_cost=5.0,
            shipping_cost=0.0
        )
        assert "(Boosted for $10.0 min margin)" not in res['reasoning']


class TestListingAIAgentThreadsCOGS:
    def test_get_final_pricing_passes_acquisition_cost(self):
        from backend.app.services.listing_ai_agent import ListingAIAgent
        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent.pricing_engine = MagicMock()
        agent._default_shipping_cost = 6.50
        agent.pricing_engine.get_price_with_comps.return_value = {
            'suggested_price': 49.99,
            'comps': [],
            'reasoning': 'Comp median',
            'source': 'comps',
            'confidence': 'high',
            'confidence_reason': '',
            'projected_profit': 30.0,
        }

        res = agent.get_final_pricing(
            title="Vintage Camera",
            condition="Used - Good",
            ai_suggested_price="50.00",
            user_price=None,
            acquisition_cost=15.0
        )

        agent.pricing_engine.get_price_with_comps.assert_called_once()
        call_kwargs = agent.pricing_engine.get_price_with_comps.call_args.kwargs
        assert call_kwargs['acquisition_cost'] == 15.0
        assert res['projected_profit'] == 30.0
