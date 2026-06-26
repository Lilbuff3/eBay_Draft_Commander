import pytest
from unittest.mock import patch, MagicMock
from backend.app.services.processor_service import ProcessorService

@pytest.fixture
def processor():
    return ProcessorService()

@pytest.fixture
def mock_job_obj():
    job = MagicMock()
    job.folder_path = "dummy/path"
    # Ensure all required properties are present to bypass earlier checks
    # But since we just want to test create_listing we might need to mock internal methods
    return job

def test_promotion_hook_enabled_success(processor, monkeypatch):
    # Mock settings manager
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda k, d=None: 'true' if k == 'PROMOTED_LISTINGS_ENABLED' else '5.5' if k == 'PROMOTED_LISTINGS_AD_RATE' else d
    monkeypatch.setattr('backend.app.services.processor_service.get_settings_manager', lambda: mock_settings)
    
    # Mock Marketing API
    mock_marketing_api_instance = MagicMock()
    mock_marketing_api_instance.promote_listing.return_value = {'success': True}
    monkeypatch.setattr('backend.app.services.processor_service.MarketingAPI', lambda: mock_marketing_api_instance)

    # We need to test the hook specifically inside create_listing. To avoid all the AI analysis,
    # let's just mock everything up to _create_trading_api_listing.
    
    # Wait, instead of mocking everything inside create_listing which is huge and fragile,
    # let's just mock all the dependencies.
    monkeypatch.setattr(processor, '_metadata_condition', lambda x: 'USED_EXCELLENT')
    monkeypatch.setattr(processor, '_determine_condition', lambda *args: 'USED_EXCELLENT')
    monkeypatch.setattr('pathlib.Path.exists', lambda self: True)
    monkeypatch.setattr('pathlib.Path.iterdir', lambda self: [MagicMock(suffix='.jpg')])
    
    mock_ai_agent = MagicMock()
    mock_ai_agent.analyze_item.return_value = {
        'success': True,
        'title': 'Test Item',
        'raw_description': 'desc',
        'item_specifics': {},
        'ai_suggested_price': 10.0
    }
    mock_ai_agent.get_final_pricing.return_value = {'price': 10.0, 'timing': 0}
    processor.ai_agent = mock_ai_agent
    
    mock_category_mapper = MagicMock()
    mock_category_mapper.get_category.return_value = {'id': '123', 'name': 'Cat'}
    processor.category_mapper = mock_category_mapper
    
    monkeypatch.setattr(processor, '_validate_and_enrich_specifics', lambda *args, **kwargs: [])
    monkeypatch.setattr(processor, '_render_listing_template', lambda *args, **kwargs: {'html': '', 'timing': 0})
    
    mock_image_processor = MagicMock()
    mock_image_processor.upload_images.return_value = {'urls': ['url1'], 'timing': 0}
    processor.image_processor = mock_image_processor
    
    monkeypatch.setattr('backend.app.services.processor_service.sanitize_numeric_aspects', lambda *args, **kwargs: None)
    
    # Mock the trading API result to return success and listing_id
    monkeypatch.setattr(processor, '_create_trading_api_listing', lambda **kwargs: {'success': True, 'listing_id': '111222333', 'status': 'Active', 'timing': 0})
    
    job_obj = MagicMock()
    job_obj.folder_path = "dummy/path"
    job_obj.ai_data = {}
    
    result = processor.create_listing(job_obj)
    
    assert result['success'] is True
    assert result['listing_id'] == '111222333'
    
    mock_marketing_api_instance.promote_listing.assert_called_once_with('111222333', 5.5)

def test_promotion_hook_disabled(processor, monkeypatch):
    # Mock settings manager
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda k, d=None: 'false' if k == 'PROMOTED_LISTINGS_ENABLED' else d
    monkeypatch.setattr('backend.app.services.processor_service.get_settings_manager', lambda: mock_settings)
    
    mock_marketing_api_instance = MagicMock()
    monkeypatch.setattr('backend.app.services.processor_service.MarketingAPI', lambda: mock_marketing_api_instance)

    # Setup the same mocks
    monkeypatch.setattr(processor, '_metadata_condition', lambda x: 'USED_EXCELLENT')
    monkeypatch.setattr(processor, '_determine_condition', lambda *args: 'USED_EXCELLENT')
    monkeypatch.setattr('pathlib.Path.exists', lambda self: True)
    monkeypatch.setattr('pathlib.Path.iterdir', lambda self: [MagicMock(suffix='.jpg')])
    mock_ai_agent = MagicMock()
    mock_ai_agent.analyze_item.return_value = {'success': True, 'title': 'Test Item', 'raw_description': 'desc', 'item_specifics': {}, 'ai_suggested_price': 10.0}
    mock_ai_agent.get_final_pricing.return_value = {'price': 10.0, 'timing': 0}
    processor.ai_agent = mock_ai_agent
    mock_category_mapper = MagicMock()
    mock_category_mapper.get_category.return_value = {'id': '123', 'name': 'Cat'}
    processor.category_mapper = mock_category_mapper
    monkeypatch.setattr(processor, '_validate_and_enrich_specifics', lambda *args, **kwargs: [])
    monkeypatch.setattr(processor, '_render_listing_template', lambda *args, **kwargs: {'html': '', 'timing': 0})
    mock_image_processor = MagicMock()
    mock_image_processor.upload_images.return_value = {'urls': ['url1'], 'timing': 0}
    processor.image_processor = mock_image_processor
    monkeypatch.setattr('backend.app.services.processor_service.sanitize_numeric_aspects', lambda *args, **kwargs: None)
    monkeypatch.setattr(processor, '_create_trading_api_listing', lambda **kwargs: {'success': True, 'listing_id': '111222333', 'status': 'Active', 'timing': 0})
    
    job_obj = MagicMock()
    result = processor.create_listing(job_obj)
    
    assert result['success'] is True
    mock_marketing_api_instance.promote_listing.assert_not_called()

def test_promotion_hook_failure_does_not_block(processor, monkeypatch):
    # Mock settings manager
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda k, d=None: 'true' if k == 'PROMOTED_LISTINGS_ENABLED' else '5.0' if k == 'PROMOTED_LISTINGS_AD_RATE' else d
    monkeypatch.setattr('backend.app.services.processor_service.get_settings_manager', lambda: mock_settings)
    
    mock_marketing_api_instance = MagicMock()
    mock_marketing_api_instance.promote_listing.side_effect = Exception("API Down")
    monkeypatch.setattr('backend.app.services.processor_service.MarketingAPI', lambda: mock_marketing_api_instance)

    # Setup the same mocks
    monkeypatch.setattr(processor, '_metadata_condition', lambda x: 'USED_EXCELLENT')
    monkeypatch.setattr(processor, '_determine_condition', lambda *args: 'USED_EXCELLENT')
    monkeypatch.setattr('pathlib.Path.exists', lambda self: True)
    monkeypatch.setattr('pathlib.Path.iterdir', lambda self: [MagicMock(suffix='.jpg')])
    mock_ai_agent = MagicMock()
    mock_ai_agent.analyze_item.return_value = {'success': True, 'title': 'Test Item', 'raw_description': 'desc', 'item_specifics': {}, 'ai_suggested_price': 10.0}
    mock_ai_agent.get_final_pricing.return_value = {'price': 10.0, 'timing': 0}
    processor.ai_agent = mock_ai_agent
    mock_category_mapper = MagicMock()
    mock_category_mapper.get_category.return_value = {'id': '123', 'name': 'Cat'}
    processor.category_mapper = mock_category_mapper
    monkeypatch.setattr(processor, '_validate_and_enrich_specifics', lambda *args, **kwargs: [])
    monkeypatch.setattr(processor, '_render_listing_template', lambda *args, **kwargs: {'html': '', 'timing': 0})
    mock_image_processor = MagicMock()
    mock_image_processor.upload_images.return_value = {'urls': ['url1'], 'timing': 0}
    processor.image_processor = mock_image_processor
    monkeypatch.setattr('backend.app.services.processor_service.sanitize_numeric_aspects', lambda *args, **kwargs: None)
    monkeypatch.setattr(processor, '_create_trading_api_listing', lambda **kwargs: {'success': True, 'listing_id': '111222333', 'status': 'Active', 'timing': 0})
    
    job_obj = MagicMock()
    result = processor.create_listing(job_obj)
    
    assert result['success'] is True
    assert result['listing_id'] == '111222333'
    mock_marketing_api_instance.promote_listing.assert_called_once()
