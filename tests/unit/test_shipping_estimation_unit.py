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


class TestMediaMailDetection:
    """Books/media should use Media Mail shipping rate ($3.50) not standard."""

    def test_book_category_returns_media_mail_cost(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(category_id="261186") == 3.50

    def test_isbn_present_returns_media_mail_cost(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(isbn="9781579656362") == 3.50

    def test_electronics_uses_ai_package_size(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(package_size="heavy") == 15.00

    def test_small_item_from_weight(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(estimated_weight_lbs=0.5) == 4.50

    def test_medium_item_from_weight(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(estimated_weight_lbs=2.0) == 6.50

    def test_fallback_returns_default(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost() == 6.50

    def test_media_mail_overrides_package_size(self):
        """Even if AI says 'medium', a book should use Media Mail rate."""
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(isbn="1234567890", package_size="medium") == 3.50
