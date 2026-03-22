"""Test that research-enhanced SEO title is preferred over vision-only title."""
import pytest
from unittest.mock import patch, MagicMock


class TestTitleSelection:
    """Verify title priority: user_title > seo_title > suggested_title."""

    def test_seo_title_preferred_over_suggested(self):
        """When Phase 3 produces seo_title, it should be used over Phase 1 suggested_title."""
        from backend.app.services.listing_ai_agent import ListingAIAgent

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent.ai_analyzer = MagicMock()
        agent.pricing_engine = MagicMock()
        agent._default_shipping_cost = 6.50

        # Simulate AI data with both titles
        ai_data = {
            'listing': {
                'suggested_title': 'Generic Vision Title',
                'confidence_score': 0.9,
            },
            'seo_title': 'Aiwa CA-30 Boombox Stereo Receiver Cassette Radio Used',
            'identification': {'brand': 'Aiwa', 'model': 'CA-30'},
            'item_specifics': {},
        }
        agent.ai_analyzer.analyze_with_research = MagicMock(return_value=ai_data)

        job = MagicMock()
        job.ai_data = None  # Force re-analysis
        job.user_title = None
        job.user_description = None
        job.user_price = None
        job.folder_path = '/tmp/test'

        with patch('backend.app.services.listing_ai_agent.taxonomy') as mock_tax:
            mock_tax.get_category_suggestions = MagicMock(return_value='')
            result = agent.analyze_item(job, images=['/tmp/img.jpg'], condition='USED_GOOD')

        assert result['success']
        assert result['title'] == 'Aiwa CA-30 Boombox Stereo Receiver Cassette Radio Used'

    def test_user_title_overrides_seo_title(self):
        """User-provided title always wins."""
        from backend.app.services.listing_ai_agent import ListingAIAgent

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent.ai_analyzer = MagicMock()
        agent.pricing_engine = MagicMock()
        agent._default_shipping_cost = 6.50

        ai_data = {
            'listing': {'suggested_title': 'Vision Title', 'confidence_score': 0.9},
            'seo_title': 'SEO Title',
            'identification': {},
            'item_specifics': {},
        }
        agent.ai_analyzer.analyze_with_research = MagicMock(return_value=ai_data)

        job = MagicMock()
        job.ai_data = None
        job.user_title = 'My Custom Title'
        job.user_description = None
        job.user_price = None
        job.folder_path = '/tmp/test'

        with patch('backend.app.services.listing_ai_agent.taxonomy') as mock_tax:
            mock_tax.get_category_suggestions = MagicMock(return_value='')
            result = agent.analyze_item(job, images=['/tmp/img.jpg'], condition='USED_GOOD')

        assert result['title'] == 'My Custom Title'

    def test_falls_back_to_suggested_when_no_seo(self):
        """When Phase 3 doesn't produce seo_title, fall back to Phase 1."""
        from backend.app.services.listing_ai_agent import ListingAIAgent

        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent.ai_analyzer = MagicMock()
        agent.pricing_engine = MagicMock()
        agent._default_shipping_cost = 6.50

        ai_data = {
            'listing': {'suggested_title': 'Vision Title', 'confidence_score': 0.9},
            'identification': {},
            'item_specifics': {},
        }
        agent.ai_analyzer.analyze_with_research = MagicMock(return_value=ai_data)

        job = MagicMock()
        job.ai_data = None
        job.user_title = None
        job.user_description = None
        job.user_price = None
        job.folder_path = '/tmp/test'

        with patch('backend.app.services.listing_ai_agent.taxonomy') as mock_tax:
            mock_tax.get_category_suggestions = MagicMock(return_value='')
            result = agent.analyze_item(job, images=['/tmp/img.jpg'], condition='USED_GOOD')

        assert result['title'] == 'Vision Title'
