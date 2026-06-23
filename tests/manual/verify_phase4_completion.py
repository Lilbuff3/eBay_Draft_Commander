import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from backend.app import create_app
from backend.app.services.queue_manager import QueueManager, JobStatus
from backend.app.services.processor_service import ProcessorService

# --- Mocks ---

@pytest.fixture
def mock_dependencies():
    with patch('backend.app.services.processor_service.eBayService') as mock_ebay, \
         patch('backend.app.services.processor_service.ListingAIAgent') as mock_agent, \
         patch('backend.app.services.processor_service.ImageProcessor') as mock_image_processor, \
         patch('backend.app.services.processor_service.get_template_manager') as mock_tmpl:
        
        # Setup specific mock behaviors
        
        # Listing AI Agent: returns basic analysis data
        def mock_analyze_item(job_obj, images, condition, log_callback=None):
            title = job_obj.user_title or "AI Generated Title"
            raw_desc = job_obj.user_description or "AI Description"
            return {
                "success": True,
                "ai_data": {
                    "listing": {
                        "suggested_title": "AI Generated Title",
                        "suggested_price": "20.00",
                        "description": "AI Description"
                    },
                    "identification": {"brand": "TestBrand", "category_id": "12345"},
                    "condition": {"state": "Used", "is_nos": False}
                },
                "title": title,
                "raw_description": raw_desc,
                "item_specifics": {"Brand": "TestBrand"},
                "ai_suggested_price": "20.00",
                "shipping_cost": 6.50,
                "category_id": "12345",
                "confidence_score": 0.9
            }
        mock_agent.return_value.analyze_item.side_effect = mock_analyze_item
        
        # Listing AI Agent: returns a price
        def mock_get_final_pricing(title, condition, ai_suggested_price, user_price, **kwargs):
            price = user_price if user_price else "20.00"
            return {
                "price": str(price),
                "timing": 0.1,
                "comps": [],
                "reasoning": "Mock price reasoning",
                "source": "mock"
            }
        mock_agent.return_value.get_final_pricing.side_effect = mock_get_final_pricing
        
        # eBay: succeeds in creation
        mock_ebay.return_value.create_trading_api_listing.return_value = {
            "success": True,
            "item_id": "LIST_123",
            "status": "Scheduled"
        }
        
        # Image Processor: returns dummy URLs
        mock_image_processor.return_value.upload_images.return_value = {
            "urls": ["http://img.com/1.jpg"],
            "timing": 0.2
        }
        
        # Template Manager: returns mock HTML
        mock_tmpl.return_value.render_description.return_value = "<html>Rendered HTML</html>"
        
        yield {
            'ebay': mock_ebay.return_value, 
            'agent': mock_agent.return_value, 
            'image_processor': mock_image_processor.return_value
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
    4. Successful Completion and Description Preview
    """
    client = app_context['client']
    qm = app_context['qm']
    inbox = app_context['inbox']
    mocks = app_context['mocks']
    
    # Pause queue processing to prevent background worker from starting before overrides are applied
    qm.pause()

    # 1. Create Job (Simulate 'Create from Photos')
    job_folder = inbox / "web_upload_test_123"
    job_folder.mkdir()
    (job_folder / "test_image.jpg").touch()
    
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
    
    # Resume processing now that overrides are set in DB
    qm.resume()
    
    # Verify updates were persisted to DB
    updated_job = qm.get_job_by_id(job.id)
    assert updated_job.user_title == "User Overridden Title"
    assert float(updated_job.user_price) == 55.0
    assert updated_job.job_metadata.get('fulfillment_policy') == "POLICY_VIP_SHIPPING"

    
    # 3. Wait for processing to complete
    import time
    timeout = 5
    start = time.time()
    while job.status in [JobStatus.PENDING, JobStatus.PROCESSING] and time.time() - start < timeout:
        time.sleep(0.1)
        # Fetch updated job details to refresh state from DB
        db_job = qm.get_job_by_id(job.id)
        if db_job:
            job = db_job
        
    assert job.status in [JobStatus.COMPLETED, JobStatus.SCHEDULED]
    assert job.listing_id == "LIST_123"
    assert float(job.price) == 55.0 # Should match override
    
    # 4. Verify eBay Calls used Overrides
    create_args = mocks['ebay'].create_trading_api_listing.call_args[0]
    item_payload = create_args[0]
    assert item_payload['title'] == "User Overridden Title"
    assert float(item_payload['price']) == 55.0
    assert item_payload['fulfillment_policy_id'] == "POLICY_VIP_SHIPPING"
    assert item_payload['condition_id'] == "1000" # NEW is mapped to 1000

    # 5. Verify Preview Endpoint works as expected
    preview_res = client.get(f"/api/job/{job.id}/preview")
    assert preview_res.status_code == 200
    assert "<html>Rendered HTML</html>" in preview_res.text

    print("\n✅ Verification Successful: API -> Overrides -> Processor -> eBay Draft & Preview")
