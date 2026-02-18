
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from backend.app.services.processor_service import ProcessorService
from backend.app.services.queue_manager import QueueManager
from backend.app import create_app

@pytest.fixture
def test_app(tmp_path):
    # Set up a minimal app for context-aware services
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['EBAY_MERCHANT_LOCATION'] = 'TEST_LOC'
    app.config['EBAY_FULFILLMENT_POLICY'] = 'SHIP_TEST'
    app.config['EBAY_PAYMENT_POLICY'] = 'PAY_TEST'
    app.config['EBAY_RETURN_POLICY'] = 'RET_TEST'
    return app

@pytest.fixture
def mock_deps():
    with patch('backend.app.services.processor_service.eBayService') as mock_ebay, \
         patch('backend.app.services.processor_service.AIAnalyzer') as mock_ai, \
         patch('backend.app.services.processor_service.PricingEngine') as mock_pricing, \
         patch('backend.app.services.processor_service.upload_folder') as mock_upload, \
         patch('backend.app.services.processor_service.get_template_manager') as mock_tmpl:
        
        # Setup basic successes for constructor
        mock_inventory = MagicMock()
        mock_inventory.create_inventory_item.return_value = ({}, 200)
        mock_inventory.create_offer.return_value = ({'offerId': 'OFFER_ABC'}, 200)
        mock_ebay.return_value.inventory_service = mock_inventory
        mock_ebay.return_value.publish_listing.return_value = ({'listingId': 'LIST_XYZ'}, 200)
        
        mock_pricing.return_value.get_price_with_comps.return_value = {"suggested_price": "25.00"}
        mock_upload.return_value = ["img.jpg"]
        mock_tmpl.return_value.render_description.return_value = "<html>Test</html>"
        
        yield {
            'ai': mock_ai.return_value,
            'ebay': mock_ebay.return_value,
            'pricing': mock_pricing.return_value,
            'inventory': mock_inventory
        }

def test_condition_mapping_from_folders(mock_deps, tmp_path):
    """Test that condition is correctly overridden based on parent folder name"""
    # Create folder structure: inbox/New Old Stock/item_folder
    inbox = tmp_path / "inbox"
    nos_folder = inbox / "New Old Stock"
    item_folder = nos_folder / "test_item"
    item_folder.mkdir(parents=True)
    
    # We need a dummy image to pass the 'images' check
    (item_folder / "test.jpg").touch()
    
    service = ProcessorService()
    
    mock_deps['ai'].analyze_with_research.return_value = {
        "identification": {"confidence_score": 90},
        "listing": {"suggested_title": "Test Item", "suggested_price": "100.00"},
        "item_specifics": {"Brand": "Sony"}
    }
    
    # Configure create_listing_bundle mock
    mock_deps['ebay'].create_listing_bundle.return_value = {
        'success': True, 
        'listing_id': '123', 
        'offer_id': '456', 
        'status': 'published'
    }

    from flask import Flask
    app = Flask(__name__)
    app.config['EBAY_MERCHANT_LOCATION'] = 'DEFAULT'
    with app.app_context():
        result = service.create_listing(str(item_folder))
            
    assert result['success'] == True
    
    # Check that create_listing_bundle was called with correct item_data (containing condition)
    bundle_call = mock_deps['ebay'].create_listing_bundle.call_args
    assert bundle_call is not None
    
    # create_listing_bundle(sku=..., item_data=..., ...)
    # args are likely passed as kwargs or positional. 
    # Based on processor_service.py: 
    # create_listing_bundle(sku=sku, item_data=item_data, offer_data=offer_payload, auto_publish=should_publish)
    
    kwargs = bundle_call.kwargs
    item_data = kwargs['item_data']
    
    assert item_data['condition'] == 'NEW_OTHER'

def test_aspect_cleaning_truncation(mock_deps, tmp_path):
    """Test that aspects are truncated to 65 chars and OEM brand is replaced"""
    long_val = "A" * 100
    mock_ai_data = {
        "identification": {"confidence_score": 90},
        "listing": {"suggested_title": "Test", "suggested_price": "10.00"},
        "item_specifics": {
            "Brand": "OEM",
            "LongAspect": long_val,
            "ShortAspect": "Normal"
        }
    }
    
    (tmp_path / "img.jpg").touch()
    service = ProcessorService()
    mock_deps['ai'].analyze_with_research.return_value = mock_ai_data
    
    mock_deps['ebay'].create_listing_bundle.return_value = {'success': True}

    from flask import Flask
    app = Flask(__name__)
    app.config['EBAY_MERCHANT_LOCATION'] = 'DEFAULT'
    with app.app_context():
        service.create_listing(str(tmp_path))
            
    bundle_call = mock_deps['ebay'].create_listing_bundle.call_args
    assert bundle_call is not None
    
    aspects = bundle_call.kwargs['item_data']['product']['aspects']
    
    assert aspects['Brand'] == ['Unbranded']
    assert len(aspects['LongAspect'][0]) == 65
    assert aspects['LongAspect'][0].endswith("...")

def test_strict_mode_ai_failure(mock_deps, tmp_path):
    """Test that if AI fails, listing creation stops (Strict Mode)"""
    mock_ai_data = {"error": "AI Timeout"}
    (tmp_path / "img.jpg").touch()
    service = ProcessorService()
    mock_deps['ai'].analyze_with_research.return_value = mock_ai_data
    
    result = service.create_listing(str(tmp_path))
        
    assert result['success'] == False
    assert result['error_type'] == "AI_Analysis_Failed"
