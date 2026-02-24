"""
Tests for business logic in ProcessorService.

Tests verify: condition mapping from folder structure, aspect cleaning/truncation,
and strict-mode AI failure handling.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from backend.app.services.processor_service import ProcessorService
from backend.app.services.queue_manager import QueueManager
from backend.app import create_app


def _make_mock_job(folder_path, **overrides):
    """Create a mock QueueJob object for testing."""
    job = MagicMock()
    job.folder_path = str(folder_path)
    job.job_metadata = overrides.get('job_metadata', {})
    job.user_condition = overrides.get('user_condition', None)
    job.user_price = overrides.get('user_price', None)
    job.user_title = overrides.get('user_title', None)
    job.scheduled_time = overrides.get('scheduled_time', None)
    job.ai_data = overrides.get('ai_data', {})
    return job


@pytest.fixture
def test_app(tmp_path):
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
         patch('backend.app.services.processor_service.ListingAIAgent') as mock_ai_agent, \
         patch('backend.app.services.processor_service.ImageProcessor') as mock_img_proc, \
         patch('backend.app.services.processor_service.get_template_manager') as mock_tmpl, \
         patch('backend.app.services.processor_service.CategoryMapper') as mock_cat:

        # AI Agent defaults
        agent = mock_ai_agent.return_value
        agent.analyze_item.return_value = {
            'success': True,
            'title': 'Test Item',
            'raw_description': 'A test item description.',
            'item_specifics': {'Brand': 'Sony'},
            'ai_suggested_price': '100.00'
        }
        agent.get_final_pricing.return_value = {
            'price': '100.00',
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
        mock_tmpl.return_value.render_description.return_value = '<html>Test</html>'

        # eBay Trading API
        mock_ebay.return_value.create_trading_api_listing.return_value = {
            'success': True,
            'item_id': 'LIST_123',
            'status': 'active'
        }

        yield {
            'ai_agent': agent,
            'ebay': mock_ebay.return_value,
            'img_proc': mock_img_proc.return_value,
            'template': mock_tmpl.return_value,
            'category': mock_cat.return_value
        }


def test_condition_mapping_from_folders(test_app, mock_deps, tmp_path):
    """Test that condition is correctly derived from parent folder name"""
    # Create folder structure: New Old Stock/test_item/
    nos_folder = tmp_path / "New Old Stock"
    item_folder = nos_folder / "test_item"
    item_folder.mkdir(parents=True)
    (item_folder / "test.jpg").touch()

    mock_job = _make_mock_job(item_folder)  # no user_condition, no metadata condition
    service = ProcessorService()

    with test_app.app_context():
        result = service.create_listing(mock_job)

    assert result['success'] is True

    # Verify the Trading API was called with the correct condition_id
    # "New Old Stock" maps to NEW_OTHER, which maps to condition_id '1500'
    call_args = mock_deps['ebay'].create_trading_api_listing.call_args
    assert call_args is not None
    item_data = call_args[0][0] if call_args[0] else call_args[1].get('item_data', {})
    assert item_data['condition_id'] == '1500'  # NEW_OTHER


def test_aspect_cleaning_truncation(test_app, mock_deps, tmp_path):
    """Test that aspects are truncated to 65 chars and OEM brand is replaced"""
    long_val = "A" * 100
    mock_deps['ai_agent'].analyze_item.return_value = {
        'success': True,
        'title': 'Test Aspect Item',
        'raw_description': 'Testing aspect cleaning.',
        'item_specifics': {
            'Brand': 'OEM',
            'LongAspect': long_val,
            'ShortAspect': 'Normal'
        },
        'ai_suggested_price': '10.00'
    }
    mock_deps['ai_agent'].get_final_pricing.return_value = {
        'price': '10.00',
        'timing': 0.1
    }

    item_folder = tmp_path / "test_aspects"
    item_folder.mkdir()
    (item_folder / "img.jpg").touch()

    mock_job = _make_mock_job(item_folder)
    service = ProcessorService()

    with test_app.app_context():
        result = service.create_listing(mock_job)

    # Check the Trading API call for cleaned aspects
    call_args = mock_deps['ebay'].create_trading_api_listing.call_args
    assert call_args is not None
    item_data = call_args[0][0] if call_args[0] else call_args[1].get('item_data', {})
    aspects = item_data['item_specifics']

    # OEM → Unbranded
    assert aspects['Brand'] == ['Unbranded']
    # Long value truncated to 65 chars
    assert len(aspects['LongAspect'][0]) == 65
    # Short value preserved
    assert aspects['ShortAspect'] == ['Normal']


def test_strict_mode_ai_failure(mock_deps, tmp_path):
    """Test that if AI analysis fails, listing creation stops with error"""
    mock_deps['ai_agent'].analyze_item.return_value = {
        'success': False,
        'error': 'AI analysis returned no valid data'
    }

    item_folder = tmp_path / "test_ai_fail"
    item_folder.mkdir()
    (item_folder / "img.jpg").touch()

    mock_job = _make_mock_job(item_folder)
    service = ProcessorService()

    result = service.create_listing(mock_job)

    assert result['success'] is False
    assert 'error_message' in result

    # eBay should never be called if AI fails
    mock_deps['ebay'].create_trading_api_listing.assert_not_called()
