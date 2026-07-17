"""Price-discovery mode for no-comp items.

Instead of stalling a no-comp item (commercial parts etc.) in pending_review,
the processor lists it HIGH (research-range high, else suggested * markup)
with Best Offer + an aggressive markdown ladder tag, and sends an inform-only
WhatsApp text. Hard guards (user_approved bypass, market_ai_conflict, dup)
keep their existing behavior.

Seam: processor_service.create_listing, strictly AFTER the user_approved
bypass and BEFORE the pending_review return.
"""
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from backend.app.services.price_discovery import (
    is_discovery_eligible, compute_discovery_price,
)
from backend.app.services.processor_service import ProcessorService


# ---------------------------------------------------------------- pure fns

class TestEligibility:
    @pytest.mark.parametrize('source', [
        'ai_grounded_research', 'research_market_price', 'ai_estimate'])
    def test_no_comp_ai_sources_eligible(self, source):
        assert is_discovery_eligible({'comps': [], 'source': source}, True) is True

    def test_conflict_not_eligible(self):
        pr = {'comps': [{'price': 10}], 'source': 'market_ai_conflict'}
        assert is_discovery_eligible(pr, True) is False

    def test_comp_backed_source_not_eligible(self):
        pr = {'comps': [{'price': 10}], 'source': 'market_data_keyword'}
        assert is_discovery_eligible(pr, True) is False

    def test_eligible_source_with_comps_not_eligible(self):
        pr = {'comps': [{'price': 10}], 'source': 'ai_estimate'}
        assert is_discovery_eligible(pr, True) is False

    def test_disabled_flag_wins(self):
        assert is_discovery_eligible({'comps': [], 'source': 'ai_estimate'}, False) is False

    def test_failed_manual_not_eligible(self):
        pr = {'comps': [], 'source': 'failed_requires_manual'}
        assert is_discovery_eligible(pr, True) is False

    def test_user_override_not_eligible(self):
        pr = {'comps': [], 'source': 'user_override'}
        assert is_discovery_eligible(pr, True) is False


class TestComputeDiscoveryPrice:
    def test_research_high_wins_when_above_markup(self):
        result = compute_discovery_price(
            {'price': '100.00'},
            {'research': {'market_price': {'low': 80, 'mid': 120, 'high': 200}}},
            markup_pct=25)
        assert result['list_price'] == pytest.approx(200.0)
        assert result['basis'] == 'research_high'

    def test_markup_fallback_without_research(self):
        result = compute_discovery_price({'price': '100.00'}, {}, markup_pct=25)
        assert result['list_price'] == pytest.approx(125.0)
        assert result['basis'] == 'markup'

    def test_markup_wins_when_research_high_is_lower(self):
        result = compute_discovery_price(
            {'price': '100.00'},
            {'research': {'market_price': {'high': 90}}},
            markup_pct=25)
        assert result['list_price'] == pytest.approx(125.0)
        assert result['basis'] == 'markup'

    def test_zero_price_and_no_research_returns_none(self):
        assert compute_discovery_price({'price': '0.00'}, {}, markup_pct=25) is None

    def test_zero_price_with_research_high_uses_research(self):
        result = compute_discovery_price(
            {'price': '0.00'},
            {'research': {'market_price': {'high': 60}}},
            markup_pct=25)
        assert result['list_price'] == pytest.approx(60.0)
        assert result['basis'] == 'research_high'

    def test_garbage_inputs_return_none(self):
        assert compute_discovery_price({'price': None}, None, markup_pct=25) is None


class TestSettings:
    def test_defaults_present(self):
        from backend.app.core.settings_manager import SettingsManager
        assert SettingsManager.DEFAULTS.get('PRICE_DISCOVERY_ENABLED') == 'true'
        assert SettingsManager.DEFAULTS.get('PRICE_DISCOVERY_MARKUP_PCT') == '25'
        assert SettingsManager.DEFAULTS.get('PRICE_DISCOVERY_DECLINE_PCT') == '50'

    def test_keys_in_automation_category(self):
        from backend.app.core.settings_manager import SettingsManager
        automation = SettingsManager.SETTING_CATEGORIES['Automation']
        for key in ('PRICE_DISCOVERY_ENABLED', 'PRICE_DISCOVERY_MARKUP_PCT',
                    'PRICE_DISCOVERY_DECLINE_PCT'):
            assert key in automation


# ------------------------------------------------------- processor seam

@pytest.fixture
def processor():
    return ProcessorService()


def _wire_mocks(processor, monkeypatch, title="Ross 4800AR CPU Board", price=100.0,
                comps=None, source="ai_estimate", confidence='low',
                discovery_enabled='true'):
    """Same harness as test_pre_listing_guardrails_hook, plus pricing
    confidence + discovery settings."""
    monkeypatch.setattr(processor, '_metadata_condition', lambda x: 'USED_EXCELLENT')
    monkeypatch.setattr(processor, '_determine_condition', lambda *args: 'USED_EXCELLENT')
    monkeypatch.setattr('pathlib.Path.exists', lambda self: True)
    monkeypatch.setattr('pathlib.Path.iterdir', lambda self: [MagicMock(suffix='.jpg')])

    mock_ai_agent = MagicMock()
    mock_ai_agent.analyze_item.return_value = {
        'success': True, 'title': title, 'raw_description': 'desc',
        'item_specifics': {'Brand': 'Ross'}, 'ai_suggested_price': price,
    }
    mock_ai_agent.get_final_pricing.return_value = {
        'price': price, 'timing': 0, 'comps': comps or [], 'source': source,
        'reasoning': '', 'confidence': confidence, 'confidence_reason': 'no comps',
    }
    processor.ai_agent = mock_ai_agent

    mock_category_mapper = MagicMock()
    mock_category_mapper.get_category.return_value = {'id': '123', 'name': 'Cat'}
    processor.category_mapper = mock_category_mapper

    monkeypatch.setattr(processor, '_validate_and_enrich_specifics', lambda *a, **k: [])
    monkeypatch.setattr(processor, '_render_listing_template', lambda *a, **k: {'html': '', 'timing': 0})

    mock_image_processor = MagicMock()
    mock_image_processor.upload_images.return_value = {'urls': ['url1'], 'timing': 0}
    processor.image_processor = mock_image_processor

    monkeypatch.setattr('backend.app.services.processor_service.sanitize_numeric_aspects',
                        lambda *a, **k: None)

    trading_api_mock = MagicMock(return_value={
        'success': True, 'listing_id': '111222333', 'status': 'Active', 'timing': 0,
    })
    monkeypatch.setattr(processor, '_create_trading_api_listing', trading_api_mock)

    settings_values = {
        'PROMOTED_LISTINGS_ENABLED': 'false',
        'PRICE_DISCOVERY_ENABLED': discovery_enabled,
        'PRICE_DISCOVERY_MARKUP_PCT': '25',
        'PRICE_DISCOVERY_DECLINE_PCT': '50',
    }
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda k, d=None: settings_values.get(k, d)
    monkeypatch.setattr('backend.app.core.settings_manager.get_settings_manager',
                        lambda: mock_settings)

    notify_mock = MagicMock(return_value=True)
    monkeypatch.setattr('backend.app.services.whatsapp_notify.notify_whatsapp', notify_mock)
    monkeypatch.setattr('backend.app.services.whatsapp_notify.get_notify_destination',
                        lambda meta: 'owner-chat')
    return trading_api_mock, notify_mock


def _make_job_obj(job_metadata=None, ai_data=None):
    job_obj = MagicMock()
    job_obj.folder_path = "dummy/path"
    job_obj.ai_data = ai_data or {}
    job_obj.job_metadata = job_metadata if job_metadata is not None else {}
    job_obj.user_price = None
    job_obj.user_condition = None
    job_obj.scheduled_time = None
    return job_obj


class TestDiscoveryBranch:
    def test_no_comp_item_lists_at_markup_price_instead_of_review(self, processor, monkeypatch):
        trading_api_mock, notify_mock = _wire_mocks(processor, monkeypatch)
        job_obj = _make_job_obj()

        result = processor.create_listing(job_obj)

        assert result.get('status') != 'pending_review'
        assert result['success'] is True
        trading_api_mock.assert_called_once()
        assert trading_api_mock.call_args.kwargs['final_price'] == '125.00'
        assert job_obj.job_metadata['price_discovery']['base_price'] == 100.0
        assert job_obj.job_metadata['price_discovery']['basis'] == 'markup'
        notify_mock.assert_called_once()

    def test_research_high_price_used_when_present(self, processor, monkeypatch):
        trading_api_mock, _ = _wire_mocks(processor, monkeypatch)
        job_obj = _make_job_obj(
            ai_data={'research': {'market_price': {'high': 200}}})

        result = processor.create_listing(job_obj)

        assert result['success'] is True
        assert trading_api_mock.call_args.kwargs['final_price'] == '200.00'
        assert job_obj.job_metadata['price_discovery']['basis'] == 'research_high'

    def test_discovery_passes_aggressive_decline_pct(self, processor, monkeypatch):
        trading_api_mock, _ = _wire_mocks(processor, monkeypatch)
        job_obj = _make_job_obj()

        processor.create_listing(job_obj)

        assert trading_api_mock.call_args.kwargs.get('best_offer_decline_pct') == pytest.approx(50.0)

    def test_conflict_still_routes_to_review(self, processor, monkeypatch):
        trading_api_mock, _ = _wire_mocks(
            processor, monkeypatch,
            comps=[{'price': 10.0}], source='market_ai_conflict')
        job_obj = _make_job_obj()

        result = processor.create_listing(job_obj)

        assert result.get('status') == 'pending_review'
        trading_api_mock.assert_not_called()

    def test_disabled_setting_keeps_review_behavior(self, processor, monkeypatch):
        trading_api_mock, _ = _wire_mocks(
            processor, monkeypatch, discovery_enabled='false')
        job_obj = _make_job_obj()

        result = processor.create_listing(job_obj)

        assert result.get('status') == 'pending_review'
        trading_api_mock.assert_not_called()

    def test_user_approved_price_never_re_priced(self, processor, monkeypatch):
        trading_api_mock, _ = _wire_mocks(processor, monkeypatch)
        job_obj = _make_job_obj(job_metadata={'user_approved': True})

        result = processor.create_listing(job_obj)

        assert result['success'] is True
        # bypass path: original price, no discovery tag
        assert trading_api_mock.call_args.kwargs['final_price'] == 100.0
        assert 'price_discovery' not in job_obj.job_metadata

    def test_unpriceable_item_still_pauses(self, processor, monkeypatch):
        """Pricing that failed outright (failed_requires_manual) is not a
        discovery candidate — even though the DEFAULT_PRICE fallback fills in
        a placeholder price, the job keeps the old pending_review routing."""
        trading_api_mock, _ = _wire_mocks(
            processor, monkeypatch, price=0.0, source='failed_requires_manual')
        job_obj = _make_job_obj()

        result = processor.create_listing(job_obj)

        assert result.get('status') == 'pending_review'
        trading_api_mock.assert_not_called()


class TestDiscoveryMessage:
    def test_builder_mentions_price_and_reply_hint(self):
        from backend.app.services.whatsapp_notify import build_price_discovery_message
        msg = build_price_discovery_message('Ross CPU Board', 125.0, 'markup')
        assert '125.00' in msg
        assert 'cancel last' in msg.lower()


class TestDeclineOverrideWiring:
    def test_create_trading_listing_uses_override_pct(self, monkeypatch):
        settings_values = {
            'BEST_OFFER_ENABLED': 'true',
            'BEST_OFFER_AUTO_ACCEPT_PCT': '90',
            'BEST_OFFER_AUTO_DECLINE_PCT': '60',
        }
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda k, d=None: settings_values.get(k, d)
        monkeypatch.setattr('backend.app.core.settings_manager.get_settings_manager',
                            lambda: mock_settings)

        processor = ProcessorService()
        captured = {}

        def fake_create(item_data, schedule_time=None):
            captured['item_data'] = item_data
            return {'success': True, 'item_id': '111', 'status': 'Active'}

        processor.ebay_service = MagicMock()
        processor.ebay_service.create_trading_api_listing.side_effect = fake_create

        app = Flask(__name__)
        app.config.update(EBAY_PAYMENT_POLICY='p', EBAY_RETURN_POLICY='r',
                          EBAY_FULFILLMENT_POLICY='f', EBAY_POSTAL_CODE='93611')
        with app.app_context():
            processor._create_trading_api_listing(
                title='Widget', final_price='100.00', condition='USED_EXCELLENT',
                category_id='267', html_description='<p>x</p>', image_urls=['u'],
                item_specifics={}, shipping_policy=None,
                best_offer_decline_pct=50.0)

        assert captured['item_data']['best_offer_minimum'] == pytest.approx(50.0)
        assert captured['item_data']['best_offer_auto_accept'] == pytest.approx(90.0)
