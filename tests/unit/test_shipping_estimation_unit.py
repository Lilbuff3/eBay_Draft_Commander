import sys
from pathlib import Path

# Add project root to sys.path
# File is at root/tests/unit/test_...py, so parents[2] is root
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from backend.app.services.listing_ai_agent import ListingAIAgent


class TestShippingEstimation:
    """Unit tests for shipping cost estimation logic."""

    def setup_method(self):
        self.agent = ListingAIAgent()

    def test_light_item_small_size(self):
        ai_data = {"identification": {"package_size": "small", "estimated_weight_lbs": 0.5}}
        assert self.agent._calculate_shipping_cost(ai_data) == 4.50

    def test_medium_item(self):
        ai_data = {"identification": {"package_size": "medium", "estimated_weight_lbs": 1.5}}
        assert self.agent._calculate_shipping_cost(ai_data) == 6.50

    def test_heavy_item_board_game(self):
        ai_data = {"identification": {"package_size": "large", "estimated_weight_lbs": 5.0}}
        assert self.agent._calculate_shipping_cost(ai_data) == 10.00

    def test_very_heavy_item(self):
        ai_data = {"identification": {"package_size": "heavy", "estimated_weight_lbs": 12.0}}
        assert self.agent._calculate_shipping_cost(ai_data) == 15.00

    def test_size_missing_weight_provided(self):
        ai_data = {"identification": {"estimated_weight_lbs": 8.0}}
        assert self.agent._calculate_shipping_cost(ai_data) == 10.00

    def test_weight_under_1lb_size_missing(self):
        ai_data = {"identification": {"estimated_weight_lbs": 0.8}}
        assert self.agent._calculate_shipping_cost(ai_data) == 4.50

    def test_both_missing_fallback(self):
        ai_data = {"identification": {}}
        assert self.agent._calculate_shipping_cost(ai_data) == self.agent._default_shipping_cost
