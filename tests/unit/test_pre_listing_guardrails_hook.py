"""
Tests for the pre-submit listing-quality guardrail hook in
ProcessorService.create_listing.

Right before the eBay Trading API call, create_listing now calls
apply_pre_listing_guardrails(job_obj, price=..., source=..., comps=...) using
the pricing_result already computed earlier in the method (get_final_pricing).
Title/aspects are auto-fixed in place; a price outlier routes the job to
pending_review (mirroring the existing review-routing result shape that
queue_manager.py:917 maps to JobStatus.PENDING_REVIEW) instead of submitting
to eBay.
"""
from unittest.mock import MagicMock

import pytest

from backend.app.services.processor_service import ProcessorService


@pytest.fixture
def processor():
    return ProcessorService()


def _wire_common_mocks(processor, monkeypatch, title="Test Item", price=10.0,
                        comps=None, source="market_data_isbn", item_specifics=None):
    """Mock every create_listing dependency up to (and including) the
    guardrail hook + trading API call, following the pattern established in
    test_promoted_listings_hook.py."""
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
        'price': price, 'timing': 0, 'comps': comps or [], 'source': source, 'reasoning': '',
    }
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

    trading_api_mock = MagicMock(return_value={
        'success': True, 'listing_id': '111222333', 'status': 'Active', 'timing': 0,
    })
    monkeypatch.setattr(processor, '_create_trading_api_listing', trading_api_mock)

    # Promoted-listings hook (runs after a successful trading API call) reads
    # settings via get_settings_manager(); avoid touching the real .env file.
    # PRICE_DISCOVERY_ENABLED is pinned off: these tests guard the classic
    # review-routing behavior (discovery-off path); discovery-on behavior is
    # covered in test_price_discovery.py.
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda k, d=None: (
        'false' if k in ('PROMOTED_LISTINGS_ENABLED', 'PRICE_DISCOVERY_ENABLED') else d)
    monkeypatch.setattr('backend.app.core.settings_manager.get_settings_manager', lambda: mock_settings)

    return trading_api_mock


def _make_job_obj(folder_path="dummy/path", job_metadata=None):
    job_obj = MagicMock()
    job_obj.folder_path = folder_path
    job_obj.ai_data = {}
    job_obj.job_metadata = job_metadata or {}
    job_obj.user_price = None
    job_obj.user_condition = None
    job_obj.scheduled_time = None
    return job_obj


class TestPreListingGuardrailHook:
    def test_clean_job_proceeds_to_listing_with_cleaned_title(self, processor, monkeypatch):
        """A clean job (good title, valid brand, comp-backed reasonable
        price) is unaffected by the guardrail and lists normally."""
        trading_api_mock = _wire_common_mocks(
            processor, monkeypatch,
            title="Aiwa CSD-ES227 Stereo Boombox Cassette Player",
            price=45.0,
            comps=[{"price": 40.0}, {"price": 42.0}, {"price": 50.0}],
            source="market_data_isbn",
            item_specifics={"Brand": "Aiwa"},
        )
        job_obj = _make_job_obj()

        result = processor.create_listing(job_obj)

        assert result['success'] is True
        assert result.get('status') != 'pending_review'
        assert result['listing_id'] == '111222333'
        trading_api_mock.assert_called_once()

    def test_dirty_title_and_brand_autofixed_before_listing(self, processor, monkeypatch):
        """A malformed title and a blocklisted brand are auto-fixed in place
        and the cleaned values are what actually get submitted to eBay."""
        trading_api_mock = _wire_common_mocks(
            processor, monkeypatch,
            title="Duracell AA Batteries (Alkaline,",
            price=12.0,
            comps=[{"price": 10.0}, {"price": 11.0}],
            source="market_data_isbn",
            item_specifics={"Brand": "Signed"},
        )
        job_obj = _make_job_obj()

        result = processor.create_listing(job_obj)

        assert result['success'] is True
        assert result['title'] == "Duracell AA Batteries"
        submitted_specifics = trading_api_mock.call_args.kwargs['item_specifics']
        assert submitted_specifics['Brand'] == 'Unbranded'

    def test_price_outlier_routes_to_pending_review_instead_of_listing(self, processor, monkeypatch):
        """A no-comp price far above PRICE_REVIEW_THRESHOLD (the $1091.99
        vintage-shears case from the spec) routes to pending_review and the
        eBay Trading API is never called."""
        trading_api_mock = _wire_common_mocks(
            processor, monkeypatch,
            title="Vintage Shears",
            price=1091.99,
            comps=[],
            source="ai_estimate",
            item_specifics={"Brand": "Unbranded"},
        )
        job_obj = _make_job_obj()

        result = processor.create_listing(job_obj)

        assert result.get('status') == 'pending_review'
        assert result.get('success') is True
        assert 'review_reason' in result or 'error_message' in result
        trading_api_mock.assert_not_called()

    def test_comp_backed_price_over_3x_median_routes_to_pending_review(self, processor, monkeypatch):
        """The (b) signal -- price > 3x comp median -- also routes to review,
        even when source looks comp-backed."""
        trading_api_mock = _wire_common_mocks(
            processor, monkeypatch,
            title="Widget",
            price=100.0,
            comps=[{"price": 10.0}, {"price": 12.0}, {"price": 11.0}],
            source="market_data_isbn",
            item_specifics={"Brand": "Acme"},
        )
        job_obj = _make_job_obj()

        result = processor.create_listing(job_obj)

        assert result.get('status') == 'pending_review'
        trading_api_mock.assert_not_called()

    def test_user_approved_job_overrides_price_flag_and_lists(self, processor, monkeypatch):
        """An approved job must NOT bounce back to pending_review: the approve
        endpoints set job_metadata['user_approved'] and the guardrail re-fires
        on reprocess (same price, same missing comps), so without the override
        the job ping-pongs between approval and review forever."""
        trading_api_mock = _wire_common_mocks(
            processor, monkeypatch,
            title="Ross 4800AR-003-02 Frame CPU Processor Board",
            price=1255.99,
            comps=[],
            source="ai_estimate",
            item_specifics={"Brand": "Ross"},
        )
        job_obj = _make_job_obj(job_metadata={'user_approved': True})

        result = processor.create_listing(job_obj)

        assert result.get('status') != 'pending_review'
        assert result['success'] is True
        assert result['listing_id'] == '111222333'
        trading_api_mock.assert_called_once()

    def test_pending_review_result_carries_title_and_price(self, processor, monkeypatch):
        """Verify the pending_review result shape includes the fields
        queue_manager.py's review-routing branch reads off the result dict
        (title, price, condition) so the job record stays informative."""
        _wire_common_mocks(
            processor, monkeypatch,
            title="Vintage Shears",
            price=1091.99,
            comps=[],
            source="ai_estimate",
        )
        job_obj = _make_job_obj()

        result = processor.create_listing(job_obj)

        assert result.get('status') == 'pending_review'
        assert result.get('title') == 'Vintage Shears'
        assert result.get('price') is not None
