"""
The eBay description must be rendered from the SAME title and aspects that get
submitted -- i.e. after every mutation pass, not before.

create_listing mutates analysis['title'] and analysis['item_specifics'] in three
places after the AI hands them over:
  - the required-aspects guard (fills missing aspects),
  - sanitize_numeric_aspects (coerces/drops NUMBER aspects),
  - apply_pre_listing_guardrails (clean_title + normalize_aspects).

Rendering before those passes ships a listing whose title says one thing and
whose description body says another -- the buyer reads the stale version.

Mirrors the mocking style of test_pre_listing_guardrails_hook.py, except
_render_listing_template is a real-ish stub that echoes the title/aspects it was
handed, so the test can prove WHICH values reached the renderer.
"""
from unittest.mock import MagicMock

import pytest

from backend.app.services.processor_service import ProcessorService


@pytest.fixture
def processor():
    return ProcessorService()


def _wire_mocks(processor, monkeypatch, title, item_specifics=None,
                price=45.0, comps=None, source="market_data_isbn"):
    """Wire create_listing's collaborators, leaving the render -> guardrail ->
    submit ordering under test. Returns (trading_api_mock, render_calls)."""
    monkeypatch.setattr(processor, '_metadata_condition', lambda x: 'USED_EXCELLENT')
    monkeypatch.setattr(processor, '_determine_condition', lambda *args: 'USED_EXCELLENT')
    monkeypatch.setattr('pathlib.Path.exists', lambda self: True)
    monkeypatch.setattr('pathlib.Path.iterdir', lambda self: [MagicMock(suffix='.jpg')])

    mock_ai_agent = MagicMock()
    mock_ai_agent.analyze_item.return_value = {
        'success': True,
        'title': title,
        'raw_description': 'desc',
        'item_specifics': item_specifics if item_specifics is not None else {},
        'ai_suggested_price': price,
    }
    mock_ai_agent.get_final_pricing.return_value = {
        'price': price, 'timing': 0, 'comps': comps or [{"price": 40.0}, {"price": 42.0}],
        'source': source, 'reasoning': '',
    }
    processor.ai_agent = mock_ai_agent

    mock_category_mapper = MagicMock()
    mock_category_mapper.get_category.return_value = {'id': '123', 'name': 'Cat'}
    processor.category_mapper = mock_category_mapper

    monkeypatch.setattr(processor, '_validate_and_enrich_specifics', lambda *args, **kwargs: [])

    # Echo renderer: records exactly what it was handed and bakes the title into
    # the html, the way the real template does.
    render_calls = []

    def _fake_render(title, description, images, aspects, condition, research=None):
        render_calls.append({'title': title, 'aspects': dict(aspects or {})})
        rows = ''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in (aspects or {}).items())
        return {'html': f'<h1>{title}</h1><table>{rows}</table>', 'timing': 0}

    monkeypatch.setattr(processor, '_render_listing_template', _fake_render)

    mock_image_processor = MagicMock()
    mock_image_processor.upload_images.return_value = {'urls': ['url1'], 'timing': 0}
    processor.image_processor = mock_image_processor

    monkeypatch.setattr(
        'backend.app.services.processor_service.sanitize_numeric_aspects',
        lambda *args, **kwargs: None,
    )

    trading_api_mock = MagicMock(return_value={
        'success': True, 'listing_id': '111222333', 'status': 'Active', 'timing': 0,
    })
    monkeypatch.setattr(processor, '_create_trading_api_listing', trading_api_mock)

    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda k, d=None: 'false' if k == 'PROMOTED_LISTINGS_ENABLED' else d
    monkeypatch.setattr('backend.app.core.settings_manager.get_settings_manager', lambda: mock_settings)

    return trading_api_mock, render_calls


def _make_job_obj(job_metadata=None):
    job_obj = MagicMock()
    job_obj.folder_path = "dummy/path"
    job_obj.ai_data = {}
    job_obj.job_metadata = job_metadata or {}
    job_obj.user_price = None
    job_obj.user_condition = None
    job_obj.scheduled_time = None
    return job_obj


class TestDescriptionTitleSync:
    def test_submitted_title_appears_in_submitted_description(self, processor, monkeypatch):
        """The title eBay shows and the title inside the description body must
        be the same string. A title needing clean_title() is the case that
        breaks when the render runs too early."""
        trading_api_mock, _ = _wire_mocks(
            processor, monkeypatch,
            title="Duracell AA Batteries (Alkaline,",
            item_specifics={"Brand": "Duracell"},
        )

        result = processor.create_listing(_make_job_obj())

        assert result['success'] is True
        submitted_title = trading_api_mock.call_args.kwargs['title']
        submitted_html = trading_api_mock.call_args.kwargs['html_description']

        # clean_title strips the dangling "(Alkaline," fragment.
        assert submitted_title == "Duracell AA Batteries"
        # Exact-match the heading, not a substring: the stale title
        # ("...Batteries (Alkaline,") CONTAINS the cleaned one as a prefix, so
        # `submitted_title in html` passes even when the bug is present.
        assert f'<h1>{submitted_title}</h1>' in submitted_html, (
            f"description heading is not the submitted title. "
            f"submitted title={submitted_title!r}, html={submitted_html!r}"
        )

    def test_renderer_receives_the_cleaned_title(self, processor, monkeypatch):
        """Directly pin the ordering: the renderer must be handed the
        post-guardrail title, not the raw AI one."""
        _, render_calls = _wire_mocks(
            processor, monkeypatch,
            title="Sencore Sencore LC102 Capacitor Analyzer",
            item_specifics={"Brand": "Sencore"},
        )

        processor.create_listing(_make_job_obj())

        assert len(render_calls) == 1
        # clean_title collapses the repeated leading word.
        assert render_calls[0]['title'] == "Sencore LC102 Capacitor Analyzer"

    def test_renderer_receives_normalized_aspects(self, processor, monkeypatch):
        """normalize_aspects maps a blocklisted brand to 'Unbranded'. The
        description's spec table must show the normalized value, not the junk
        one the AI produced."""
        trading_api_mock, render_calls = _wire_mocks(
            processor, monkeypatch,
            title="Vintage Hand Shears",
            item_specifics={"Brand": "Signed"},
        )

        processor.create_listing(_make_job_obj())

        assert render_calls[0]['aspects'].get('Brand') == 'Unbranded'
        submitted_html = trading_api_mock.call_args.kwargs['html_description']
        assert 'Signed' not in submitted_html

    def test_pending_review_job_still_gets_a_description(self, processor, monkeypatch):
        """The review gate returns early. Rendering must happen before that
        return, or jobs sitting in the Review Queue have no description to
        show."""
        job_obj = _make_job_obj()
        _wire_mocks(
            processor, monkeypatch,
            title="Vintage Shears",
            item_specifics={"Brand": "Unbranded"},
            price=1091.99,
            comps=[],
            source="ai_estimate",
        )

        result = processor.create_listing(job_obj)

        assert result.get('status') == 'pending_review'
        assert job_obj.description, "review-routed job was left with no description"
        assert 'Vintage Shears' in job_obj.description
