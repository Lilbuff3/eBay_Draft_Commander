"""Trading API safety tests: XML escaping, defensive Ack parse, dedupe-safe retry.

Guards the money paths in backend/app/services/ebay/trading.py:
- unescaped picture URLs / numeric fields must not malform listing XML
- a 200 response without an Ack must not raise AttributeError
- an ambiguous AddFixedPriceItem failure (timeout after send) must check the
  SKU on eBay before retrying, so a committed item is never listed twice
"""
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

import pytest
import requests as requests_lib

from backend.app.core.constants import TRADING_API_MAX_RETRIES
from backend.app.services.ebay.trading import TradingService

NS = "urn:ebay:apis:eBLBaseComponents"

ADD_SUCCESS_XML = f'''<?xml version="1.0" encoding="utf-8"?>
<AddFixedPriceItemResponse xmlns="{NS}">
  <Ack>Success</Ack>
  <ItemID>1234567890</ItemID>
  <StartTime>2026-07-11T00:00:00.000Z</StartTime>
</AddFixedPriceItemResponse>'''

NO_ACK_XML = f'''<?xml version="1.0" encoding="utf-8"?>
<AddFixedPriceItemResponse xmlns="{NS}">
  <Timestamp>2026-07-11T00:00:00.000Z</Timestamp>
</AddFixedPriceItemResponse>'''

REVISE_SUCCESS_XML = f'''<?xml version="1.0" encoding="utf-8"?>
<ReviseFixedPriceItemResponse xmlns="{NS}"><Ack>Success</Ack></ReviseFixedPriceItemResponse>'''

END_SUCCESS_XML = f'''<?xml version="1.0" encoding="utf-8"?>
<EndFixedPriceItemResponse xmlns="{NS}">
  <Ack>Success</Ack>
  <EndTime>2026-07-11T01:00:00.000Z</EndTime>
</EndFixedPriceItemResponse>'''

ITEM = {
    'title': 'Test & Item <cool>',
    'description': 'desc',
    'price': 12.34,
    'category_id': '267',
    'condition_id': '3000',
    'sku': 'DC-DEADBEEF',
    'image_urls': ['https://covers.example.com/img.jpg?a=1&b=2&c=<x>'],
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


class TestXmlEscaping:
    def test_ampersand_in_picture_url_yields_parseable_xml(self, token_patch):
        captured = {}

        def fake_post(call_name, xml_request, ambiguous_guard=None):
            captured['xml'] = xml_request
            return _fake_response(), None

        with patch('backend.app.services.ebay.trading._post_trading_request', side_effect=fake_post):
            result = TradingService().add_fixed_price_item(ITEM)

        assert result['success'] is True
        root = ET.fromstring(captured['xml'])  # unescaped & or < would raise here
        urls = [e.text for e in root.iter(f'{{{NS}}}PictureURL')]
        assert urls == ['https://covers.example.com/img.jpg?a=1&b=2&c=<x>']

    def test_numeric_fields_round_trip(self, token_patch):
        captured = {}

        def fake_post(call_name, xml_request, ambiguous_guard=None):
            captured['xml'] = xml_request
            return _fake_response(), None

        with patch('backend.app.services.ebay.trading._post_trading_request', side_effect=fake_post):
            TradingService().add_fixed_price_item(ITEM)

        root = ET.fromstring(captured['xml'])
        assert root.find(f'.//{{{NS}}}CategoryID').text == '267'
        assert root.find(f'.//{{{NS}}}StartPrice').text == '12.34'
        assert root.find(f'.//{{{NS}}}ConditionID').text == '3000'


class TestDefensiveAck:
    def test_missing_ack_returns_failure_not_raise(self, token_patch):
        with patch('backend.app.services.ebay.trading._post_trading_request',
                   return_value=(_fake_response(text=NO_ACK_XML), None)), \
             patch.object(TradingService, '_find_listing_by_sku', return_value=None):
            result = TradingService().add_fixed_price_item(ITEM)
        assert result['success'] is False

    def test_missing_ack_recovers_committed_item(self, token_patch):
        """200 + no Ack is ambiguous: if the SKU is live, report that item."""
        existing = {'listingId': '999', 'sku': 'DC-DEADBEEF', 'startTime': 'T'}
        with patch('backend.app.services.ebay.trading._post_trading_request',
                   return_value=(_fake_response(text=NO_ACK_XML), None)), \
             patch.object(TradingService, '_find_listing_by_sku', return_value=existing):
            result = TradingService().add_fixed_price_item(ITEM)
        assert result['success'] is True
        assert result['item_id'] == '999'
        assert result.get('recovered_duplicate') is True


class TestDedupeGuard:
    def test_timeout_recovers_existing_listing_without_replay(self, token_patch):
        calls = {'n': 0}

        def raise_timeout(*a, **k):
            calls['n'] += 1
            raise requests_lib.exceptions.Timeout('boom')

        existing = {'listingId': '999', 'sku': 'DC-DEADBEEF', 'startTime': 'T'}
        with patch('backend.app.services.ebay.trading.requests.post', side_effect=raise_timeout), \
             patch('backend.app.services.ebay.trading.time.sleep'), \
             patch.object(TradingService, '_find_listing_by_sku', return_value=existing):
            result = TradingService().add_fixed_price_item(ITEM)

        assert result['success'] is True
        assert result['item_id'] == '999'
        assert result.get('recovered_duplicate') is True
        assert calls['n'] == 1  # committed item must never be re-added

    def test_timeout_without_existing_listing_retries_then_fails(self, token_patch):
        calls = {'n': 0}

        def raise_timeout(*a, **k):
            calls['n'] += 1
            raise requests_lib.exceptions.Timeout('boom')

        with patch('backend.app.services.ebay.trading.requests.post', side_effect=raise_timeout), \
             patch('backend.app.services.ebay.trading.time.sleep'), \
             patch.object(TradingService, '_find_listing_by_sku', return_value=None):
            result = TradingService().add_fixed_price_item(ITEM)

        assert result['success'] is False
        assert calls['n'] == TRADING_API_MAX_RETRIES + 1


class TestEndReviseRetry:
    def test_revise_retries_on_500(self, token_patch):
        responses = [_fake_response(500, 'server error'),
                     _fake_response(200, REVISE_SUCCESS_XML)]
        with patch('backend.app.services.ebay.trading.requests.post', side_effect=responses), \
             patch('backend.app.services.ebay.trading.time.sleep'):
            result = TradingService().revise_fixed_price_item('123456', price=9.99)
        assert result['success'] is True
        assert result['price'] == 9.99

    def test_end_retries_on_500(self, token_patch):
        responses = [_fake_response(500, 'server error'),
                     _fake_response(200, END_SUCCESS_XML)]
        with patch('backend.app.services.ebay.trading.requests.post', side_effect=responses), \
             patch('backend.app.services.ebay.trading.time.sleep'):
            result = TradingService().end_fixed_price_item('123456')
        assert result['success'] is True
