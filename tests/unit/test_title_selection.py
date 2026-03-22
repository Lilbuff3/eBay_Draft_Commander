"""Test title selection: user > best of (seo, suggested) > fallback."""
import pytest
from unittest.mock import patch, MagicMock


def _make_agent():
    from backend.app.services.listing_ai_agent import ListingAIAgent
    agent = ListingAIAgent.__new__(ListingAIAgent)
    agent.ai_analyzer = MagicMock()
    agent.pricing_engine = MagicMock()
    agent._default_shipping_cost = 6.50
    return agent


def _make_job(user_title=None):
    job = MagicMock()
    job.ai_data = None
    job.user_title = user_title
    job.user_description = None
    job.user_price = None
    job.folder_path = '/tmp/test'
    return job


def _run(agent, job, ai_data):
    agent.ai_analyzer.analyze_with_research = MagicMock(return_value=ai_data)
    with patch('backend.app.services.listing_ai_agent.taxonomy') as mock_tax:
        mock_tax.get_category_suggestions = MagicMock(return_value='')
        return agent.analyze_item(job, images=['/tmp/img.jpg'], condition='USED_GOOD')


class TestTitleSelection:
    """Verify title priority: user > longest(seo, suggested) > fallback."""

    def test_longer_seo_title_wins(self):
        """When SEO title is longer than suggested, SEO title is used."""
        agent = _make_agent()
        ai_data = {
            'listing': {'suggested_title': 'Short', 'confidence_score': 0.9},
            'seo_title': 'Aiwa CA-30 Boombox Stereo Receiver Cassette Radio Used',
            'identification': {'brand': 'Aiwa', 'model': 'CA-30'},
            'item_specifics': {},
        }
        result = _run(agent, _make_job(), ai_data)
        assert result['success']
        assert result['title'] == 'Aiwa CA-30 Boombox Stereo Receiver Cassette Radio Used'

    def test_longer_suggested_title_wins(self):
        """When suggested title is longer than SEO title, suggested wins."""
        agent = _make_agent()
        ai_data = {
            'listing': {
                'suggested_title': 'Crossroads by Tal Ronnen Vegan Cookbook Signed First Edition',
                'confidence_score': 0.9,
            },
            'seo_title': 'Artisan Crossroads Cookbook',
            'identification': {},
            'item_specifics': {},
        }
        result = _run(agent, _make_job(), ai_data)
        assert result['title'] == 'Crossroads by Tal Ronnen Vegan Cookbook Signed First Edition'

    def test_user_title_overrides_everything(self):
        """User-provided title always wins regardless of length."""
        agent = _make_agent()
        ai_data = {
            'listing': {'suggested_title': 'Very Long Suggested Title That Should Lose', 'confidence_score': 0.9},
            'seo_title': 'Even Longer SEO Title That Should Also Lose To User',
            'identification': {},
            'item_specifics': {},
        }
        result = _run(agent, _make_job(user_title='My Custom Title'), ai_data)
        assert result['title'] == 'My Custom Title'

    def test_falls_back_to_suggested_when_no_seo(self):
        """When no seo_title exists, fall back to suggested_title."""
        agent = _make_agent()
        ai_data = {
            'listing': {'suggested_title': 'Vision Title', 'confidence_score': 0.9},
            'identification': {},
            'item_specifics': {},
        }
        result = _run(agent, _make_job(), ai_data)
        assert result['title'] == 'Vision Title'

    def test_falls_back_to_seo_when_no_suggested(self):
        """When no suggested_title exists, use seo_title."""
        agent = _make_agent()
        ai_data = {
            'listing': {'confidence_score': 0.9},
            'seo_title': 'SEO Only Title',
            'identification': {},
            'item_specifics': {},
        }
        result = _run(agent, _make_job(), ai_data)
        assert result['title'] == 'SEO Only Title'
