"""Test that web research data enriches listing descriptions."""
import pytest
from unittest.mock import MagicMock


class TestResearchDescriptionEnrichment:
    """Verify that _render_listing_template injects research sections into HTML."""

    def _make_processor(self):
        """Create a ProcessorService with mocked dependencies."""
        from backend.app.services.processor_service import ProcessorService

        svc = ProcessorService.__new__(ProcessorService)
        svc.template_manager = MagicMock()
        svc.template_manager.render_description.return_value = '<p>Base description</p>'
        return svc

    def test_no_research_returns_base_html(self):
        """Without research data, HTML should be unchanged."""
        svc = self._make_processor()
        result = svc._render_listing_template(
            'Title', 'Desc', ['http://img.jpg'], {}, 'USED_GOOD'
        )
        assert result['html'] == '<p>Base description</p>'
        assert 'timing' in result

    def test_no_research_kwarg_returns_base_html(self):
        """Passing research=None should be the same as omitting it."""
        svc = self._make_processor()
        result = svc._render_listing_template(
            'Title', 'Desc', ['http://img.jpg'], {}, 'USED_GOOD', research=None
        )
        assert result['html'] == '<p>Base description</p>'

    def test_empty_research_returns_base_html(self):
        """Empty research dict should not add any sections."""
        svc = self._make_processor()
        result = svc._render_listing_template(
            'Title', 'Desc', ['http://img.jpg'], {}, 'USED_GOOD', research={}
        )
        assert result['html'] == '<p>Base description</p>'

    def test_compatible_with_rendered(self):
        """Compatible systems should appear as a list in the HTML."""
        svc = self._make_processor()
        research = {
            'compatible_with': ['PlayStation 5', 'PlayStation 4', 'Xbox Series X'],
        }
        result = svc._render_listing_template(
            'Title', 'Desc', ['http://img.jpg'], {}, 'USED_GOOD', research=research
        )
        html = result['html']
        assert 'Compatible With' in html
        assert 'PlayStation 5' in html
        assert 'PlayStation 4' in html
        assert 'Xbox Series X' in html

    def test_compatible_with_capped_at_8(self):
        """Only first 8 compatible items should be rendered."""
        svc = self._make_processor()
        research = {
            'compatible_with': [f'Device {i}' for i in range(15)],
        }
        result = svc._render_listing_template(
            'Title', 'Desc', ['http://img.jpg'], {}, 'USED_GOOD', research=research
        )
        html = result['html']
        assert 'Device 7' in html
        assert 'Device 8' not in html

    def test_notes_rendered(self):
        """Research notes should appear in the HTML as italic text."""
        svc = self._make_processor()
        research = {
            'notes': 'This model was discontinued in 2020 and is highly sought after by collectors.',
        }
        result = svc._render_listing_template(
            'Title', 'Desc', ['http://img.jpg'], {}, 'USED_GOOD', research=research
        )
        html = result['html']
        assert 'discontinued in 2020' in html
        assert 'font-style:italic' in html

    def test_short_notes_ignored(self):
        """Notes shorter than 10 characters should not be rendered."""
        svc = self._make_processor()
        research = {'notes': 'OK'}
        result = svc._render_listing_template(
            'Title', 'Desc', ['http://img.jpg'], {}, 'USED_GOOD', research=research
        )
        assert result['html'] == '<p>Base description</p>'

    def test_both_sections_rendered(self):
        """Both compatible_with and notes should appear when present."""
        svc = self._make_processor()
        research = {
            'compatible_with': ['MacBook Pro 2021'],
            'notes': 'Universal USB-C charger with 100W PD support.',
        }
        result = svc._render_listing_template(
            'Title', 'Desc', ['http://img.jpg'], {}, 'USED_GOOD', research=research
        )
        html = result['html']
        assert 'Compatible With' in html
        assert 'MacBook Pro 2021' in html
        assert 'USB-C charger' in html

    def test_uses_inline_styles_only(self):
        """All styling must be inline (eBay strips <style> blocks on mobile)."""
        svc = self._make_processor()
        research = {
            'compatible_with': ['Device A'],
            'notes': 'Some useful research notes here for buyers.',
        }
        result = svc._render_listing_template(
            'Title', 'Desc', ['http://img.jpg'], {}, 'USED_GOOD', research=research
        )
        html = result['html']
        assert '<style' not in html
        assert 'class=' not in html
