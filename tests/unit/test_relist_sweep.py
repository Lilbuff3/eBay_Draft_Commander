"""Unsold relist sweep — nothing dies silently.

trading gains GetMyeBaySelling (UnsoldList) + RelistFixedPriceItem; the
autopilot cycle relists unsold items with one markdown step applied, honoring
the no_relist blocklist (intentional ends must not resurrect) and the
RELIST_MAX_TIMES cap. Relisting rewrites the job's listing_id so ledger and
orders joins survive the new ItemID.
"""
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.app.services.ebay.trading import TradingService

from test_autopilot_scanner import (
    BASE_SETTINGS, L, J, NOW, make_scanner, _rows,
)

NS = "urn:ebay:apis:eBLBaseComponents"

UNSOLD_XML = f'''<?xml version="1.0" encoding="utf-8"?>
<GetMyeBaySellingResponse xmlns="{NS}">
  <Ack>Success</Ack>
  <UnsoldList>
    <ItemArray>
      <Item>
        <ItemID>111</ItemID>
        <Title>Unsold Widget</Title>
        <SKU>DC-DEAD0001</SKU>
        <SellingStatus><CurrentPrice currencyID="USD">100.00</CurrentPrice></SellingStatus>
        <ListingDetails><EndTime>2026-07-10T00:00:00.000Z</EndTime></ListingDetails>
      </Item>
      <Item>
        <ItemID>222</ItemID>
        <Title>Old Book</Title>
        <SellingStatus><CurrentPrice currencyID="USD">12.00</CurrentPrice></SellingStatus>
      </Item>
    </ItemArray>
  </UnsoldList>
</GetMyeBaySellingResponse>'''

RELIST_SUCCESS_XML = f'''<?xml version="1.0" encoding="utf-8"?>
<RelistFixedPriceItemResponse xmlns="{NS}">
  <Ack>Success</Ack>
  <ItemID>999888777</ItemID>
</RelistFixedPriceItemResponse>'''


def _fake_response(text, status=200):
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
        gtm.return_value = tm
        yield tm


class TestGetUnsoldListings:
    def test_request_shape_and_parse(self, token_patch):
        captured = {}

        def fake_post(call_name, xml_request, ambiguous_guard=None):
            captured['call'] = call_name
            captured['xml'] = xml_request
            return _fake_response(UNSOLD_XML), None

        with patch('backend.app.services.ebay.trading._post_trading_request',
                   side_effect=fake_post):
            items = TradingService().get_unsold_listings(days_back=30)

        assert captured['call'] == 'GetMyeBaySelling'
        root = ET.fromstring(captured['xml'])
        unsold = root.find(f'{{{NS}}}UnsoldList')
        assert unsold is not None
        assert unsold.find(f'{{{NS}}}Include').text == 'true'
        assert unsold.find(f'{{{NS}}}DurationInDays').text == '30'

        assert len(items) == 2
        assert items[0]['item_id'] == '111'
        assert items[0]['title'] == 'Unsold Widget'
        assert items[0]['sku'] == 'DC-DEAD0001'
        assert items[0]['price'] == pytest.approx(100.0)
        assert items[1]['item_id'] == '222'

    def test_error_returns_empty(self, token_patch):
        with patch('backend.app.services.ebay.trading._post_trading_request',
                   return_value=(_fake_response('boom', status=500), None)):
            assert TradingService().get_unsold_listings() == []


class TestRelistFixedPriceItem:
    def test_relist_with_price(self, token_patch):
        captured = {}

        def fake_post(call_name, xml_request, ambiguous_guard=None):
            captured['call'] = call_name
            captured['xml'] = xml_request
            return _fake_response(RELIST_SUCCESS_XML), None

        with patch('backend.app.services.ebay.trading._post_trading_request',
                   side_effect=fake_post):
            result = TradingService().relist_fixed_price_item('111', price=95.0)

        assert captured['call'] == 'RelistFixedPriceItem'
        root = ET.fromstring(captured['xml'])
        item = root.find(f'{{{NS}}}Item')
        assert item.find(f'{{{NS}}}ItemID').text == '111'
        assert item.find(f'{{{NS}}}StartPrice').text == '95.00'
        assert result['success'] is True
        assert result['new_item_id'] == '999888777'

    def test_relist_without_price_omits_startprice(self, token_patch):
        captured = {}

        def fake_post(call_name, xml_request, ambiguous_guard=None):
            captured['xml'] = xml_request
            return _fake_response(RELIST_SUCCESS_XML), None

        with patch('backend.app.services.ebay.trading._post_trading_request',
                   side_effect=fake_post):
            TradingService().relist_fixed_price_item('111')

        root = ET.fromstring(captured['xml'])
        assert root.find(f'{{{NS}}}Item/{{{NS}}}StartPrice') is None


def _unsold(item_id='111', price=100.0, sku='DC-DEAD0001'):
    return {'item_id': item_id, 'title': 'Unsold Widget', 'price': price,
            'sku': sku, 'end_time': '2026-07-10T00:00:00.000Z'}


def make_relist_scanner(tmp_path, monkeypatch, unsold, jobs=None, settings=None):
    merged = {'RELIST_ENABLED': 'true', **(settings or {})}
    scanner, qm, trading, negotiation = make_scanner(
        tmp_path, monkeypatch, [], jobs=jobs, settings=merged)
    trading.get_unsold_listings.return_value = unsold
    trading.relist_fixed_price_item.return_value = {
        'success': True, 'new_item_id': '999888777'}
    return scanner, qm, trading


class TestRelistSweep:
    def test_unsold_item_relisted_with_markdown_step(self, tmp_path, monkeypatch):
        job = SimpleNamespace(id='j1', listing_id='111', price='100.00', job_metadata={})
        scanner, qm, trading = make_relist_scanner(
            tmp_path, monkeypatch, [_unsold()], jobs=[job])
        updates = {}
        monkeypatch.setattr(qm, 'update_job',
                            lambda jid, u: updates.setdefault(jid, u) or True)
        result = scanner.run_cycle(now=NOW)
        trading.relist_fixed_price_item.assert_called_once()
        args, kwargs = trading.relist_fixed_price_item.call_args
        assert args[0] == '111'
        assert kwargs.get('price') == pytest.approx(95.0)
        assert len(result['relists']) == 1
        assert updates['j1']['listing_id'] == '999888777'

    def test_blocklisted_item_not_relisted(self, tmp_path, monkeypatch):
        scanner, qm, trading = make_relist_scanner(
            tmp_path, monkeypatch, [_unsold()], jobs=[])
        scanner.record_action('111', 'no_relist', False, {'reason': 'manual end'}, NOW - 100)
        result = scanner.run_cycle(now=NOW)
        trading.relist_fixed_price_item.assert_not_called()
        assert result['relists'] == []

    def test_relist_cap_respected(self, tmp_path, monkeypatch):
        scanner, qm, trading = make_relist_scanner(
            tmp_path, monkeypatch, [_unsold()], jobs=[],
            settings={'RELIST_MAX_TIMES': '2'})
        scanner.record_action('111', 'relist', False, {}, NOW - 200)
        scanner.record_action('111', 'relist', False, {}, NOW - 100)
        result = scanner.run_cycle(now=NOW)
        trading.relist_fixed_price_item.assert_not_called()
        assert result['relists'] == []

    def test_dry_run_records_but_does_not_relist(self, tmp_path, monkeypatch):
        scanner, qm, trading = make_relist_scanner(
            tmp_path, monkeypatch, [_unsold()], jobs=[],
            settings={'OFFERS_MARKDOWNS_DRY_RUN': 'true'})
        result = scanner.run_cycle(now=NOW)
        trading.relist_fixed_price_item.assert_not_called()
        assert len(result['relists']) == 1
        rows = _rows(qm, 'relist')
        assert len(rows) == 1 and rows[0]['dry_run'] is True

    def test_relist_disabled_skips_fetch(self, tmp_path, monkeypatch):
        scanner, qm, trading = make_relist_scanner(
            tmp_path, monkeypatch, [_unsold()], jobs=[],
            settings={'RELIST_ENABLED': 'false'})
        scanner.run_cycle(now=NOW)
        trading.get_unsold_listings.assert_not_called()

    def test_at_floor_relists_at_current_price(self, tmp_path, monkeypatch):
        job = SimpleNamespace(id='j1', listing_id='111', price='100.00', job_metadata={})
        scanner, qm, trading = make_relist_scanner(
            tmp_path, monkeypatch, [_unsold(price=70.0)], jobs=[job])
        monkeypatch.setattr(qm, 'update_job', lambda jid, u: True)
        scanner.run_cycle(now=NOW)
        assert trading.relist_fixed_price_item.call_args.kwargs['price'] == pytest.approx(70.0)


class TestEndListingBlocklist:
    def test_manual_end_writes_no_relist_row(self):
        from flask import Flask
        from backend.app.services.ebay_service import eBayService

        service = eBayService()
        service.trading_service = MagicMock()
        service.trading_service.end_fixed_price_item.return_value = {'success': True}

        autopilot = MagicMock()
        qm = MagicMock()
        qm.autopilot = autopilot
        app = Flask(__name__)
        app.queue_manager = qm
        with app.app_context():
            result = service.end_listing('12345')

        assert result['success'] is True
        autopilot.record_action.assert_called_once()
        args = autopilot.record_action.call_args.args
        assert args[0] == '12345'
        assert args[1] == 'no_relist'

    def test_failed_end_does_not_blocklist(self):
        from flask import Flask
        from backend.app.services.ebay_service import eBayService

        service = eBayService()
        service.trading_service = MagicMock()
        service.trading_service.end_fixed_price_item.return_value = {
            'success': False, 'error': 'nope'}

        autopilot = MagicMock()
        qm = MagicMock()
        qm.autopilot = autopilot
        app = Flask(__name__)
        app.queue_manager = qm
        with app.app_context():
            service.end_listing('12345')

        autopilot.record_action.assert_not_called()
