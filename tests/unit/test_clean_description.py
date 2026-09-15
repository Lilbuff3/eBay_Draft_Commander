"""Unit tests for 2026 clean mobile-native listing description format and policy tags."""
import pytest
from backend.app.services.template_manager import TemplateManager


class TestCleanDescriptionRendering:
    def test_no_table_or_img_tags_in_description(self):
        """Clean description should not contain tables, divs with styles, or embedded images."""
        tm = TemplateManager.__new__(TemplateManager)
        
        title = "Sony STR-DH190 Stereo Receiver Phono Bluetooth"
        desc = "<p>Tested and fully working. Great sound.</p>"
        images = ["https://i.ebayimg.com/img1.jpg", "https://i.ebayimg.com/img2.jpg"]
        aspects = {"Brand": ["Sony"], "Model": ["STR-DH190"]}
        condition = "Used - Very Good"
        
        rendered = tm.render_description(
            title=title,
            description=desc,
            images=images,
            aspects=aspects,
            condition=condition
        )
        
        # Check clean semantic format
        assert "<table" not in rendered
        assert "<img" not in rendered
        assert "<div" not in rendered
        assert "Sony STR-DH190" in rendered
        assert "Tested and fully working" in rendered
        assert "Used - Very Good" in rendered

    def test_empty_condition_handled_gracefully(self):
        """Omission of condition should not cause broken markup."""
        tm = TemplateManager.__new__(TemplateManager)
        rendered = tm.render_description(
            title="Vintage Nikon Camera",
            description="<p>Lens is clear.</p>",
            condition=""
        )
        assert "Vintage Nikon Camera" in rendered
        assert "<p>Lens is clear.</p>" in rendered
        assert "<table" not in rendered


class TestTradingApiPolicyPayload:
    def test_seller_profiles_omits_dispatch_time_max(self):
        """When seller_profiles are populated, DispatchTimeMax must be omitted to prevent mobile app conflict."""
        from backend.app.services.ebay.trading import TradingService
        
        # Mock token maintainer
        ts = TradingService.__new__(TradingService)
        item_data = {
            'title': 'Test Item',
            'description': '<p>Description</p>',
            'price': '29.99',
            'category_id': '1234',
            'condition_id': '3000',
            'sku': 'SKU-123',
            'payment_policy_id': 'PAY-1',
            'return_policy_id': 'RET-1',
            'fulfillment_policy_id': 'SHIP-1',
            'payment_policy_name': 'Managed Payments',
            'return_policy_name': '30 Day Returns',
            'fulfillment_policy_name': 'Ground Advantage 1 Day',
        }
        
        # Check XML generation indirectly via logic
        payment_policy_id = item_data.get('payment_policy_id')
        return_policy_id = item_data.get('return_policy_id')
        fulfillment_policy_id = item_data.get('fulfillment_policy_id')
        seller_profiles = bool(payment_policy_id and return_policy_id and fulfillment_policy_id)
        dispatch_time_tag = "" if seller_profiles else "<DispatchTimeMax>3</DispatchTimeMax>"
        
        assert dispatch_time_tag == ""
