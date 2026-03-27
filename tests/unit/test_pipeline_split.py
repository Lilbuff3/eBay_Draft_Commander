"""Tests for two-phase pipeline split."""
import pytest
from unittest.mock import patch, MagicMock


def _make_processor():
    """Create ProcessorService with all dependencies mocked."""
    with patch('backend.app.services.processor_service.eBayService'), \
         patch('backend.app.services.processor_service.get_template_manager'), \
         patch('backend.app.services.processor_service.CategoryMapper'), \
         patch('backend.app.services.processor_service.ImageProcessor'), \
         patch('backend.app.services.processor_service.ListingAIAgent'):
        from backend.app.services.processor_service import ProcessorService
        return ProcessorService()


def _make_job(**overrides):
    """Create a mock job object with sensible defaults."""
    job = MagicMock()
    job.folder_path = overrides.get('folder_path', '/tmp/test_images')
    job.user_condition = overrides.get('user_condition', None)
    job.user_title = overrides.get('user_title', None)
    job.user_price = overrides.get('user_price', None)
    job.user_description = overrides.get('user_description', None)
    job.job_metadata = overrides.get('job_metadata', {})
    job.ai_data = overrides.get('ai_data', {})
    job.scheduled_time = overrides.get('scheduled_time', None)
    job.confidence_score = overrides.get('confidence_score', 0)
    return job


ANALYSIS_OK = {
    'success': True,
    'ai_data': {'listing': {'suggested_title': 'Test'}, 'identification': {}},
    'title': 'Test Item', 'raw_description': 'Desc', 'item_specifics': {},
    'ai_suggested_price': 25.0, 'shipping_cost': 6.50,
    'category_id': '175673', 'confidence_score': 0.9
}


class TestPipelineSplit:
    def test_no_condition_returns_awaiting(self):
        """Job with no user_condition and no folder/metadata condition pauses."""
        processor = _make_processor()
        processor.ai_agent.analyze_item.return_value = ANALYSIS_OK
        processor.category_mapper.get_category.return_value = {'id': '175673', 'name': 'Test Category'}

        job = _make_job()

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.iterdir', return_value=[MagicMock(suffix='.jpg')]), \
             patch('backend.app.services.category_correction_cache.get_correction_cache') as mock_cache:
            mock_cache.return_value.lookup.return_value = None
            result = processor.create_listing(job)

        assert result['status'] == 'awaiting_condition'
        assert result['success'] is True
        assert result['category_id'] == '175673'

    def test_user_condition_skips_gate(self):
        """Job WITH user_condition should NOT pause at awaiting_condition."""
        processor = _make_processor()
        processor.ai_agent.analyze_item.return_value = ANALYSIS_OK

        job = _make_job(user_condition='USED_GOOD')

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.iterdir', return_value=[MagicMock(suffix='.jpg')]), \
             patch('backend.app.services.category_correction_cache.get_correction_cache') as mock_cache:
            mock_cache.return_value.lookup.return_value = None
            result = processor.create_listing(job)

        # Should proceed past gate (may fail at pricing, but NOT awaiting_condition)
        assert result.get('status') != 'awaiting_condition'

    def test_ai_detected_condition_skips_gate(self):
        """If AI detects a condition, the gate should NOT fire."""
        processor = _make_processor()
        analysis_with_condition = {
            **ANALYSIS_OK,
            'ai_data': {
                'listing': {'suggested_title': 'Test'},
                'identification': {},
                'condition': {'state': 'Used - Good', 'confidence': 0.85}
            },
        }
        processor.ai_agent.analyze_item.return_value = analysis_with_condition

        job = _make_job()

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.iterdir', return_value=[MagicMock(suffix='.jpg')]), \
             patch('backend.app.services.category_correction_cache.get_correction_cache') as mock_cache:
            mock_cache.return_value.lookup.return_value = None
            result = processor.create_listing(job)

        # AI refined condition from None to USED_GOOD, so should pass the gate
        assert result.get('status') != 'awaiting_condition'
