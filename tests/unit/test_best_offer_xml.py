"""Best Offer on new listings (Trading API XML).

Guards backend/app/services/ebay/trading.py Best Offer support:
- build_best_offer_xml emits BestOfferDetails + ListingDetails floor amounts
- floors are always strictly below StartPrice (eBay rejects >=)
- a category that rejects Best Offer triggers exactly one retry without the
  Best Offer blocks — Best Offer must never brick a listing
- processor_service wires BEST_OFFER_* settings into item_data
"""
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask

from backend.app.services.ebay.trading import TradingService, build_best_offer_xml

NS = "urn:ebay:apis:eBLBaseComponents"

ADD_SUCCESS_XML = f'''<?xml version="1.0" encoding="utf-8"?>
<AddFixedPriceItemResponse xmlns="{NS}">
  <Ack>Success</Ack>
  <ItemID>1234567890</ItemID>
  <StartTime>2026-07-11T00:00:00.000Z</StartTime>
</AddFixedPriceItemResponse>'''

BEST_OFFER_REJECT_XML = f'''<?xml version="1.0" encoding="utf-8"?>
<AddFixedPriceItemResponse xmlns="{NS}">
  <Ack>Failure</Ack>
  <Errors>
    <ShortMessage>Best Offer not allowed.</ShortMessage>
    <LongMessage>Best Offer is not available for this category.</LongMessage>
    <ErrorCode>21919301</ErrorCode>
    <SeverityCode>Error</SeverityCode>
  </Errors>
</AddFixedPriceItemResponse>'''

OTHER_FAILURE_XML = f'''<?xml version="1.0" encoding="utf-8"?>
<AddFixedPriceItemResponse xmlns="{NS}">
  <Ack>Failure</Ack>
  <Errors>
    <ShortMessage>Invalid category.</ShortMessage>
    <LongMessage>The category is not valid.</LongMessage>
    <ErrorCode>87</ErrorCode>
    <SeverityCode>Error</SeverityCode>
  </Errors>
</AddFixedPriceItemResponse>'''

ITEM = {
    'title': 'Widget',
    'description': 'desc',
    'price': 20.00,
    'category_id': '267',
    'condition_id': '3000',
    'sku': 'DC-CAFEF00D',
    'best_offer_enabled': True,
    'best_offer_auto_accept': 18.00,
    'best_offer_minimum': 12.00,
}


def _fake_response(status=200, text=ADD_SUCCESS_XML):
    resp = MagicMock()
    resp.status_code = status
    resp.content = text.encode('utf-8')
    resp.text = text
    return resp


@pytest.fixture
def token_patch():
    with patch('backend.app.services.ebay.trading.get_token_manager') as gtm:
        tm = MagicMock()
        tm.get_access_token.return_value = 'FAKE_TOKEN'
        tm.force_refresh.return_value = True
        gtm.return_value = tm
        yield tm


class TestBuildBestOfferXml:
    def test_disabled_returns_empty_blocks(self):
        assert build_best_offer_xml({'price': 20.0}) == ('', '')
        assert build_best_offer_xml({'price': 20.0, 'best_offer_enabled': False}) == ('', '')

    def test_enabled_emits_details_and_floors(self):
        details, listing = build_best_offer_xml(ITEM)
        d = ET.fromstring(details)
        assert d.tag == 'BestOfferDetails'
        assert d.find('BestOfferEnabled').text == 'true'
        l = ET.fromstring(listing)
        assert l.tag == 'ListingDetails'
        accept = l.find('BestOfferAutoAcceptPrice')
        minimum = l.find('MinimumBestOfferPrice')
        assert accept.text == '18.00'
        assert accept.get('currencyID') == 'USD'
        assert minimum.text == '12.00'
        assert minimum.get('currencyID') == 'USD'

    def test_enabled_without_floors_emits_only_details(self):
        details, listing = build_best_offer_xml(
            {'price': 20.0, 'best_offer_enabled': True})
        assert '<BestOfferEnabled>true</BestOfferEnabled>' in details
        assert listing == ''

    def test_floors_clamped_strictly_below_price(self):
        item = dict(ITEM, best_offer_auto_accept=25.00, best_offer_minimum=20.00)
        _, listing = build_best_offer_xml(item)
        l = ET.fromstring(listing)
        accept = float(l.find('BestOfferAutoAcceptPrice').text)
        minimum = float(l.find('MinimumBestOfferPrice').text)
        assert accept < 20.00
        assert minimum <= accept

    def test_minimum_never_exceeds_accept(self):
        item = dict(ITEM, best_offer_auto_accept=10.00, best_offer_minimum=15.00)
        _, listing = build_best_offer_xml(item)
        l = ET.fromstring(listing)
        accept = float(l.find('BestOfferAutoAcceptPrice').text)
        minimum = float(l.find('MinimumBestOfferPrice').text)
        assert minimum <= accept

    def test_nonpositive_floors_omitted(self):
        item = dict(ITEM, best_offer_auto_accept=0, best_offer_minimum=-3)
        details, listing = build_best_offer_xml(item)
        assert '<BestOfferEnabled>true</BestOfferEnabled>' in details
        assert listing == ''


class TestAddItemBestOffer:
    def _capture_xml(self, item):
        captured = {}

        def fake_post(call_name, xml_request, ambiguous_guard=None):
            captured['xml'] = xml_request
            return _fake_response(), None

        with patch('backend.app.services.ebay.trading._post_trading_request',
                   side_effect=fake_post):
            result = TradingService().add_fixed_price_item(item)
        return result, captured['xml']

    def test_best_offer_blocks_present_in_request(self, token_patch):
        result, xml = self._capture_xml(ITEM)
        assert result['success'] is True
        root = ET.fromstring(xml)
        assert root.find(f'.//{{{NS}}}BestOfferDetails/{{{NS}}}BestOfferEnabled').text == 'true'
        assert root.find(f'.//{{{NS}}}ListingDetails/{{{NS}}}BestOfferAutoAcceptPrice').text == '18.00'
        assert root.find(f'.//{{{NS}}}ListingDetails/{{{NS}}}MinimumBestOfferPrice').text == '12.00'

    def test_no_best_offer_keys_no_blocks(self, token_patch):
        item = {k: v for k, v in ITEM.items() if not k.startswith('best_offer')}
        _, xml = self._capture_xml(item)
        root = ET.fromstring(xml)
        assert root.find(f'.//{{{NS}}}BestOfferDetails') is None
        assert root.find(f'.//{{{NS}}}ListingDetails') is None


class TestBestOfferCategoryRejection:
    def test_strip_and_retry_once_on_best_offer_rejection(self, token_patch):
        calls = []

        def fake_post(call_name, xml_request, ambiguous_guard=None):
            calls.append(xml_request)
            if len(calls) == 1:
                return _fake_response(text=BEST_OFFER_REJECT_XML), None
            return _fake_response(), None

        with patch('backend.app.services.ebay.trading._post_trading_request',
                   side_effect=fake_post):
            result = TradingService().add_fixed_price_item(dict(ITEM))

        assert len(calls) == 2
        first = ET.fromstring(calls[0])
        second = ET.fromstring(calls[1])
        assert first.find(f'.//{{{NS}}}BestOfferDetails') is not None
        assert second.find(f'.//{{{NS}}}BestOfferDetails') is None
        assert result['success'] is True
        assert result.get('best_offer_stripped') is True

    def test_other_failure_does_not_retry(self, token_patch):
        calls = []

        def fake_post(call_name, xml_request, ambiguous_guard=None):
            calls.append(xml_request)
            return _fake_response(text=OTHER_FAILURE_XML), None

        with patch('backend.app.services.ebay.trading._post_trading_request',
                   side_effect=fake_post):
            result = TradingService().add_fixed_price_item(dict(ITEM))

        assert len(calls) == 1
        assert result['success'] is False

    def test_rejection_without_best_offer_enabled_does_not_retry(self, token_patch):
        calls = []

        def fake_post(call_name, xml_request, ambiguous_guard=None):
            calls.append(xml_request)
            return _fake_response(text=BEST_OFFER_REJECT_XML), None

        item = {k: v for k, v in ITEM.items() if not k.startswith('best_offer')}
        with patch('backend.app.services.ebay.trading._post_trading_request',
                   side_effect=fake_post):
            result = TradingService().add_fixed_price_item(item)

        assert len(calls) == 1
        assert result['success'] is False


class TestBestOfferSettings:
    def test_defaults_present(self):
        from backend.app.core.settings_manager import SettingsManager
        assert SettingsManager.DEFAULTS.get('BEST_OFFER_ENABLED') == 'true'
        assert SettingsManager.DEFAULTS.get('BEST_OFFER_AUTO_ACCEPT_PCT') == '90'
        assert SettingsManager.DEFAULTS.get('BEST_OFFER_AUTO_DECLINE_PCT') == '60'

    def test_keys_in_automation_category(self):
        from backend.app.core.settings_manager import SettingsManager
        automation = SettingsManager.SETTING_CATEGORIES['Automation']
        for key in ('BEST_OFFER_ENABLED', 'BEST_OFFER_AUTO_ACCEPT_PCT',
                    'BEST_OFFER_AUTO_DECLINE_PCT'):
            assert key in automation


class TestProcessorWiring:
    def _run_create(self, monkeypatch, settings_values):
        from backend.app.services.processor_service import ProcessorService

        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda k, d=None: settings_values.get(k, d)
        monkeypatch.setattr(
            'backend.app.core.settings_manager.get_settings_manager',
            lambda: mock_settings)

        processor = ProcessorService()
        captured = {}

        def fake_create(item_data, schedule_time=None):
            captured['item_data'] = item_data
            return {'success': True, 'item_id': '111', 'status': 'Active'}

        processor.ebay_service = MagicMock()
        processor.ebay_service.create_trading_api_listing.side_effect = fake_create

        app = Flask(__name__)
        app.config.update(
            EBAY_PAYMENT_POLICY='p', EBAY_RETURN_POLICY='r',
            EBAY_FULFILLMENT_POLICY='f', EBAY_POSTAL_CODE='93611')
        with app.app_context():
            result = processor._create_trading_api_listing(
                title='Widget', final_price='20.00', condition='USED_EXCELLENT',
                category_id='267', html_description='<p>x</p>',
                image_urls=['u'], item_specifics={}, shipping_policy=None)
        assert result.get('success') is True
        return captured['item_data']

    def test_settings_drive_best_offer_fields(self, monkeypatch):
        item_data = self._run_create(monkeypatch, {
            'BEST_OFFER_ENABLED': 'true',
            'BEST_OFFER_AUTO_ACCEPT_PCT': '90',
            'BEST_OFFER_AUTO_DECLINE_PCT': '60',
        })
        assert item_data['best_offer_enabled'] is True
        assert item_data['best_offer_auto_accept'] == pytest.approx(18.00)
        assert item_data['best_offer_minimum'] == pytest.approx(12.00)

    def test_disabled_setting_omits_fields(self, monkeypatch):
        item_data = self._run_create(monkeypatch, {'BEST_OFFER_ENABLED': 'false'})
        assert not item_data.get('best_offer_enabled')
