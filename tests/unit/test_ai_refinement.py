"""
Tests for the AI-driven listing creation pipeline in ProcessorService.

Tests verify: successful end-to-end listing, AI failure handling,
and missing image handling through the current Trading API path.
"""

import pytest
from unittest.mock import MagicMock, patch
from backend.app.services.processor_service import ProcessorService
from backend.app import create_app
from backend.app.services.queue_manager import QueueManager


def _make_mock_job(folder_path, **overrides):
    """Create a mock QueueJob object for testing."""
    job = MagicMock()
    job.folder_path = str(folder_path)
    job.job_metadata = overrides.get('job_metadata', {})
    job.user_condition = overrides.get('user_condition', 'USED_GOOD')
    job.user_price = overrides.get('user_price', None)
    job.user_title = overrides.get('user_title', None)
    job.scheduled_time = overrides.get('scheduled_time', None)
    job.ai_data = overrides.get('ai_data', {})
    return job


@pytest.fixture
def mock_deps():
    with patch('backend.app.services.processor_service.eBayService') as mock_ebay, \
         patch('backend.app.services.processor_service.ListingAIAgent') as mock_ai_agent, \
         patch('backend.app.services.processor_service.ImageProcessor') as mock_img_proc, \
         patch('backend.app.services.processor_service.get_template_manager') as mock_tmpl, \
         patch('backend.app.services.processor_service.CategoryMapper') as mock_cat:

        # AI Agent defaults
        agent = mock_ai_agent.return_value
        agent.analyze_item.return_value = {
            'success': True,
            'title': 'Test Item Title',
            'raw_description': 'A quality test item in good condition.',
            'item_specifics': {'Brand': 'TestBrand'},
            'ai_suggested_price': '50.00'
        }
        agent.get_final_pricing.return_value = {
            'price': '50.00',
            'timing': 0.1
        }

        # Category mapper
        mock_cat.return_value.get_category.return_value = {
            'id': '170599',
            'name': 'Other'
        }

        # Image processor
        mock_img_proc.return_value.upload_images.return_value = {
            'urls': ['https://eps.ebay.com/img1.jpg'],
            'timing': 0.2
        }

        # Template manager
        mock_tmpl.return_value.render_description.return_value = '<html><body>Test</body></html>'

        # eBay Trading API
        mock_ebay.return_value.create_trading_api_listing.return_value = {
            'success': True,
            'item_id': 'LIST_12345',
            'status': 'active'
        }

        yield {
            'ai_agent': agent,
            'ebay': mock_ebay.return_value,
            'img_proc': mock_img_proc.return_value,
            'template': mock_tmpl.return_value,
            'category': mock_cat.return_value
        }


@pytest.fixture
def test_app(tmp_path, monkeypatch):
    # Enable auto-publish so pipeline reaches Trading API (not review queue)
    monkeypatch.setenv('AUTO_PUBLISH', 'true')
    monkeypatch.setenv('CONFIDENCE_THRESHOLD', '0')
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    return app


def test_successful_listing_creation(test_app, mock_deps, tmp_path):
    """Test full pipeline: AI analysis -> category -> pricing -> upload -> listing"""
    job_folder = tmp_path / "test_item"
    job_folder.mkdir()
    (job_folder / "photo1.jpg").touch()

    mock_job = _make_mock_job(job_folder)
    service = ProcessorService()

    with test_app.app_context():
        result = service.create_listing(mock_job)

    assert result['success'] is True
    assert result['listing_id'] == 'LIST_12345'
    assert result['price'] == '50.00'
    assert 'timing' in result

    # Verify pipeline stages were called
    mock_deps['ai_agent'].analyze_item.assert_called_once()
    mock_deps['category'].get_category.assert_called_once()
    mock_deps['ai_agent'].get_final_pricing.assert_called_once()
    mock_deps['img_proc'].upload_images.assert_called_once()
    mock_deps['ebay'].create_trading_api_listing.assert_called_once()


def test_ai_failure_stops_pipeline(test_app, mock_deps, tmp_path):
    """Test that AI analysis failure returns error and stops further processing"""
    mock_deps['ai_agent'].analyze_item.return_value = {
        'success': False,
        'error': 'Gemini API timeout'
    }

    job_folder = tmp_path / "test_item_ai_fail"
    job_folder.mkdir()
    (job_folder / "photo1.jpg").touch()

    mock_job = _make_mock_job(job_folder)
    service = ProcessorService()

    with test_app.app_context():
        result = service.create_listing(mock_job)

    assert result['success'] is False
    assert 'Gemini API timeout' in result['error_message']

    # Pipeline should stop — no category/pricing/upload/listing calls
    mock_deps['category'].get_category.assert_not_called()
    mock_deps['ai_agent'].get_final_pricing.assert_not_called()
    mock_deps['ebay'].create_trading_api_listing.assert_not_called()


def test_no_images_returns_error(test_app, mock_deps, tmp_path):
    """Test that a folder with no images returns an error"""
    job_folder = tmp_path / "empty_folder"
    job_folder.mkdir()
    # No image files

    mock_job = _make_mock_job(job_folder)
    service = ProcessorService()

    with test_app.app_context():
        result = service.create_listing(mock_job)

    assert result['success'] is False
    assert 'No images' in result['error_message']

    # Nothing should be called if no images
    mock_deps['ai_agent'].analyze_item.assert_not_called()
