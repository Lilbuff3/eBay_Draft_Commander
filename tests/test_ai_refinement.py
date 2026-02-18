
import pytest
import json
from unittest.mock import MagicMock, patch, ANY
from backend.app.services.processor_service import ProcessorService
from backend.app import create_app
from backend.app.services.queue_manager import QueueManager

@pytest.fixture
def mock_deps():
    with patch('backend.app.services.processor_service.eBayService') as mock_ebay, \
         patch('backend.app.services.processor_service.AIAnalyzer') as mock_ai, \
         patch('backend.app.services.processor_service.PricingEngine') as mock_pricing, \
         patch('backend.app.services.processor_service.upload_folder') as mock_upload, \
         patch('backend.app.services.processor_service.get_template_manager') as mock_tmpl:
        
        # Setup basic successes
        mock_inventory = MagicMock()
        mock_inventory.create_inventory_item.return_value = ({}, 200)
        mock_inventory.create_offer.return_value = ({'offerId': 'OFFER_ABC'}, 200)
        mock_ebay.return_value.inventory_service = mock_inventory
        mock_ebay.return_value.publish_listing.return_value = ({'listingId': 'LIST_XYZ'}, 200)
        
        # Configure create_listing_bundle defaults (can be overridden in tests via side_effect or specific return_value)
        mock_ebay.return_value.create_listing_bundle.return_value = {
            'success': True,
            'listing_id': 'LIST_XYZ',
            'offer_id': 'OFFER_ABC',
            'status': 'active'
        }
        
        mock_pricing.return_value.get_price_with_comps.return_value = {"suggested_price": "25.00"}
        mock_upload.return_value = ["img.jpg"]
        
        yield {
            'ai': mock_ai.return_value,
            'ebay': mock_ebay.return_value,
            'pricing': mock_pricing.return_value
        }

@pytest.fixture
def test_app(tmp_path):
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['AUTO_PUBLISH'] = True
    app.config['CONFIDENCE_THRESHOLD'] = 80
    app.config['AUTO_PUBLISH_MIN_PRICE'] = 20.00
    return app

def test_auto_publish_success(test_app, mock_deps, tmp_path):
    """Test that HIGH confidence + HIGH price triggers auto-publish"""
    # Setup High Confidence AI
    mock_deps['ai'].analyze_with_research.return_value = {
        "identification": {"confidence_score": 90}, 
        "listing": {"suggested_title": "Good Item", "suggested_price": "50.00"},
        "item_specifics": {"Brand": "Test"}
    }
    
    # Run
    service = ProcessorService()
    job_folder = tmp_path / "test_job_success"
    job_folder.mkdir()
    (job_folder / "img.jpg").touch()
    
    with test_app.app_context():
        result = service.create_listing(str(job_folder))
        
    # We verify the INTENT to auto-publish by checking the call args
    mock_deps['ebay'].create_listing_bundle.assert_called_with(
        sku=ANY, 
        item_data=ANY, 
        offer_data=ANY, 
        auto_publish=True
    )

def test_auto_publish_low_confidence(test_app, mock_deps, tmp_path):
    """Test that LOW confidence prevents auto-publish (Draft)"""
    mock_deps['ai'].analyze_with_research.return_value = {
        "identification": {"confidence_score": 50}, # Below 80
        "listing": {"suggested_title": "Ambiguous Item", "suggested_price": "50.00"},
        "item_specifics": {"Brand": "Test"}
    }
    
    service = ProcessorService()
    job_folder = tmp_path / "test_job_low_conf"
    job_folder.mkdir()
    (job_folder / "img.jpg").touch()
    
    with test_app.app_context():
        result = service.create_listing(str(job_folder))
        
    # Verify we requested auto_publish=False (Draft Mode)
    args = mock_deps['ebay'].create_listing_bundle.call_args
    assert args is not None
    assert args.kwargs['auto_publish'] == False

def test_auto_publish_low_price(test_app, mock_deps, tmp_path):
    """Test that LOW price prevents auto-publish (Draft)"""
    # High Confidence but Low Price
    mock_deps['ai'].analyze_with_research.return_value = {
        "identification": {"confidence_score": 95}, 
        "listing": {"suggested_title": "Cheap Item", "suggested_price": "10.00"},
        "item_specifics": {"Brand": "Test"}
    }
    
    # Force Pricing Engine to return $10.00
    mock_deps['pricing'].get_price_with_comps.return_value = {"suggested_price": "10.00"}
    
    service = ProcessorService()
    job_folder = tmp_path / "test_job_cheap"
    job_folder.mkdir()
    (job_folder / "img.jpg").touch()
    
    with test_app.app_context():
        result = service.create_listing(str(job_folder))
    
    # Verify we requested auto_publish=False (Draft Mode)
    args = mock_deps['ebay'].create_listing_bundle.call_args
    assert args is not None
    assert args.kwargs['auto_publish'] == False

