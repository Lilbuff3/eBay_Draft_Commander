
import pytest
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from backend.app import create_app
from backend.app.services.queue_manager import QueueManager, JobStatus
from backend.app.services.processor_service import ProcessorService

# --- Mocks ---

@pytest.fixture
def mock_dependencies():
    with patch('backend.app.services.processor_service.eBayService') as mock_ebay, \
         patch('backend.app.services.processor_service.AIAnalyzer') as mock_ai, \
         patch('backend.app.services.processor_service.PricingEngine') as mock_pricing, \
         patch('backend.app.services.processor_service.upload_folder') as mock_upload, \
         patch('backend.app.services.processor_service.get_template_manager') as mock_tmpl:
        
        # Setup specific mock behaviors
        
        # AI Analyzer: returns basic data
        mock_ai.return_value.analyze_with_research.return_value = {
            "listing": {
                "suggested_title": "AI Generated Title",
                "suggested_price": "20.00",
                "description": "AI Description"
            },
            "item_specifics": {"Brand": "TestBrand"},
            "condition": {"state": "Used", "is_nos": False}
        }
        
        # Pricing: returns a price
        mock_pricing.return_value.get_price_with_comps.return_value = {
            "suggested_price": "20.00",
            "confidence": "high"
        }
        
        # eBay: succeeds in creation
        mock_inventory = MagicMock()
        mock_inventory.create_inventory_item.return_value = ({}, 200)
        mock_inventory.create_offer.return_value = ({'offerId': 'OFFER_123'}, 200)
        mock_ebay.return_value.inventory_service = mock_inventory
        mock_ebay.return_value.publish_listing.return_value = ({'listingId': 'LIST_123'}, 200)
        
        # Image Upload: returns dummy URLs
        mock_upload.return_value = ["http://img.com/1.jpg"]
        
        yield {
            'ebay': mock_inventory,
            'ai': mock_ai.return_value, 
            'pricing': mock_pricing.return_value
        }

@pytest.fixture
def app_context(tmp_path, mock_dependencies):
    # Setup Inbox
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    
    # Init App & QM
    qm = QueueManager(base_path=tmp_path)
    qm.inbox_path = inbox # Override inbox path
    
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    app.config['INBOX_DIR'] = str(inbox)
    
    # Return context
    yield {'app': app, 'client': app.test_client(), 'qm': qm, 'inbox': inbox, 'mocks': mock_dependencies}

# --- Tests ---

def test_full_listing_lifecycle(app_context):
    """
    Verifies:
    1. Upload/Creation of Job
    2. Overriding Metadata via API
    3. Processing of Job (using overrides)
    4. Successful Completion
    """
    client = app_context['client']
    qm = app_context['qm']
    inbox = app_context['inbox']
    mocks = app_context['mocks']
    
    # 1. Create Job (Simulate 'Create from Photos')
    # We can just manually create the folder to skip file upload parsing complexity in test
    job_folder = inbox / "web_upload_test_123"
    job_folder.mkdir()
    (job_folder / "test_image.jpg").touch()
    
    # Register via QM directly or API? Let's use QM to verify internal state first
    job = qm.add_folder(str(job_folder))
    assert job.status == JobStatus.PENDING
    
    # 2. Update Metadata via API (The "Wiring" Verification)
    override_payload = {
        "title": "User Overridden Title",
        "price": "55.00",
        "description": "User custom description",
        "fulfillmentPolicy": "POLICY_VIP_SHIPPING",
        "condition": "NEW",
        "process_now": True 
    }
    
    res = client.post(f"/api/job/{job.id}/update", json=override_payload)
    assert res.status_code == 200
    assert res.json['success'] == True
    
    # Verify job.json was written
    job_json_path = job_folder / "job.json"
    assert job_json_path.exists()
    with open(job_json_path) as f:
        data = json.load(f)
    assert data['user_title'] == "User Overridden Title"
    assert data['user_price'] == "55.00"
    assert data['fulfillment_policy'] == "POLICY_VIP_SHIPPING"
    
    # 3. Processing
    # Since 'process_now' was True, and we are in a test env where threads might be tricky,
    # let's manually run the processing step to be deterministic, OR check if the logical flow triggers it.
    # The API calls `qm.start_processing()`, which starts a thread.
    # In a test, waiting for thread might be readable.
    
    # Wait for processing to complete (with timeout)
    import time
    timeout = 5
    start = time.time()
    while job.status in [JobStatus.PENDING, JobStatus.PROCESSING] and time.time() - start < timeout:
        time.sleep(0.1)
        
    assert job.status == JobStatus.COMPLETED
    assert job.offer_id == "OFFER_123"
    assert job.price == "55.00" # Should match override
    
    # 4. Verify eBay Calls used Overrides
    # Check Title
    create_args = mocks['ebay'].create_inventory_item.call_args[0]
    item_payload = create_args[1]
    assert item_payload['product']['title'] == "User Overridden Title"
    assert item_payload['condition'] == "NEW" # Condition override
    
    # Check Price (create_offer)
    offer_args = mocks['ebay'].create_offer.call_args[0]
    offer_payload = offer_args[0]
    assert offer_payload['pricingSummary']['price']['value'] == "55.00"
    assert offer_payload['listingPolicies']['fulfillmentPolicyId'] == "POLICY_VIP_SHIPPING"

    print("\n✅ Verification Successful: API -> Overrides -> Processor -> eBay Draft")
