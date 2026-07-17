"""Daily autopilot scanner: offers to watchers + stale markdown ladder.

run_cycle is pure orchestration over injected trading/negotiation mocks and a
real (tmp) listing_actions table. Dry-run (the default) must make ZERO eBay
calls while still recording rows — that audit trail is what the owner reviews
before flipping live. Live idempotency only counts live rows, so a dry-run
observation window never suppresses the first real actions.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.app.core.database import ListingActionModel
from backend.app.services.autopilot_scanner import AutopilotScanner
from backend.app.services.queue_manager import QueueManager

NOW_DT = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
NOW = NOW_DT.timestamp()

BASE_SETTINGS = {
    'OFFERS_ENABLED': 'true',
    'OFFER_DISCOUNT_PCT': '10',
    'OFFER_MIN_WATCHERS': '1',
    'MARKDOWN_ENABLED': 'true',
    'MARKDOWN_AFTER_DAYS': '14',
    'MARKDOWN_STEP_PCT': '5',
    'MARKDOWN_FLOOR_PCT': '70',
    'OFFERS_MARKDOWNS_DRY_RUN': 'false',
    'DISCOVERY_MARKDOWN_AFTER_DAYS': '7',
    'DISCOVERY_MARKDOWN_STEP_PCT': '10',
    'DISCOVERY_MARKDOWN_FLOOR_PCT': '40',
    'RELIST_ENABLED': 'false',
    'WHATSAPP_NOTIFY_CHAT_ID': '',
}


def _iso_days_ago(days):
    return (NOW_DT - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def L(listing_id='100', price=100.0, watch=0, days=20, sku='DC-AAAA1111'):
    return {'listingId': listing_id, 'sku': sku, 'title': 'Widget',
            'price': price, 'watchCount': watch,
            'startTime': _iso_days_ago(days), 'status': 'Active'}


def J(listing_id='100', price='100.00', discovery=False):
    meta = {'price_discovery': {'basis': 'markup'}} if discovery else {}
    return SimpleNamespace(listing_id=listing_id, price=price, job_metadata=meta)


def make_scanner(tmp_path, monkeypatch, listings, jobs=None, settings=None):
    qm = QueueManager(tmp_path / 'base')
    monkeypatch.setattr(qm, 'get_all_jobs', lambda: jobs or [])
    trading = MagicMock()
    trading.get_active_listings_light.return_value = ({'listings': listings}, 200)
    trading.revise_fixed_price_item.return_value = {'success': True}
    negotiation = MagicMock()
    negotiation.send_offer.return_value = {'success': True}
    values = {**BASE_SETTINGS, **(settings or {})}
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda k, d=None: values.get(k, d)
    monkeypatch.setattr('backend.app.core.settings_manager.get_settings_manager',
                        lambda: mock_settings)
    scanner = AutopilotScanner(qm, trading=trading, negotiation=negotiation)
    return scanner, qm, trading, negotiation


def _rows(qm, action_type=None):
    session = qm.SessionFactory()
    try:
        q = session.query(ListingActionModel)
        if action_type:
            q = q.filter_by(action_type=action_type)
        return [
            {'listing_id': r.listing_id, 'action_type': r.action_type,
             'dry_run': r.dry_run, 'details_json': r.details_json}
            for r in q.all()
        ]
    finally:
        session.close()


class TestOffers:
    def test_offer_sent_to_watched_listing_live(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [L(watch=2, days=5)], jobs=[J()])
        result = scanner.run_cycle(now=NOW)
        negotiation.send_offer.assert_called_once()
        assert negotiation.send_offer.call_args.args[0] == '100'
        assert float(negotiation.send_offer.call_args.args[1]) == 10.0
        assert len(result['offers']) == 1
        rows = _rows(qm, 'offer')
        assert len(rows) == 1 and rows[0]['dry_run'] is False

    def test_below_min_watchers_no_offer(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [L(watch=0, days=5)], jobs=[J()])
        result = scanner.run_cycle(now=NOW)
        negotiation.send_offer.assert_not_called()
        assert result['offers'] == []

    def test_offer_not_repeated_at_same_price(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [L(watch=2, days=5)], jobs=[J()])
        scanner.run_cycle(now=NOW)
        scanner.run_cycle(now=NOW + 86400)
        assert negotiation.send_offer.call_count == 1

    def test_reoffer_after_price_drop(self, tmp_path, monkeypatch):
        listings = [L(watch=2, days=5, price=100.0)]
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, listings, jobs=[J()])
        scanner.run_cycle(now=NOW)
        listings[0] = L(watch=2, days=6, price=95.0)  # price dropped since
        trading.get_active_listings_light.return_value = ({'listings': listings}, 200)
        scanner.run_cycle(now=NOW + 86400)
        assert negotiation.send_offer.call_count == 2
        # same price again -> no third offer
        scanner.run_cycle(now=NOW + 2 * 86400)
        assert negotiation.send_offer.call_count == 2


class TestMarkdowns:
    def test_stale_listing_marked_down(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [L(days=20, price=100.0)], jobs=[J()])
        result = scanner.run_cycle(now=NOW)
        trading.revise_fixed_price_item.assert_called_once()
        args, kwargs = trading.revise_fixed_price_item.call_args
        assert args[0] == '100'
        assert kwargs.get('price') == pytest.approx(95.0)
        assert len(result['markdowns']) == 1

    def test_fresh_listing_not_marked_down(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [L(days=5)], jobs=[J()])
        scanner.run_cycle(now=NOW)
        trading.revise_fixed_price_item.assert_not_called()

    def test_markdown_cooldown_blocks_double_step(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [L(days=20, price=100.0)], jobs=[J()])
        scanner.run_cycle(now=NOW)
        scanner.run_cycle(now=NOW + 86400)  # next day, inside 14d spacing
        assert trading.revise_fixed_price_item.call_count == 1

    def test_discovery_listing_uses_aggressive_ladder(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch,
            [L(listing_id='200', days=8, price=125.0)],
            jobs=[J(listing_id='200', price='125.00', discovery=True)])
        scanner.run_cycle(now=NOW)
        trading.revise_fixed_price_item.assert_called_once()
        assert trading.revise_fixed_price_item.call_args.kwargs['price'] == pytest.approx(112.50)

    def test_floor_respected(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch,
            [L(days=60, price=70.0)], jobs=[J(price='100.00')])
        scanner.run_cycle(now=NOW)
        trading.revise_fixed_price_item.assert_not_called()

    def test_malformed_start_time_skipped(self, tmp_path, monkeypatch):
        bad = L(days=20)
        bad['startTime'] = 'not-a-date'
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [bad], jobs=[J()])
        result = scanner.run_cycle(now=NOW)  # must not raise
        trading.revise_fixed_price_item.assert_not_called()


class TestDryRun:
    def test_dry_run_records_rows_but_no_ebay_calls(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [L(watch=3, days=20, price=100.0)], jobs=[J()],
            settings={'OFFERS_MARKDOWNS_DRY_RUN': 'true'})
        result = scanner.run_cycle(now=NOW)
        negotiation.send_offer.assert_not_called()
        trading.revise_fixed_price_item.assert_not_called()
        assert result['dry_run'] is True
        assert len(result['offers']) == 1 and len(result['markdowns']) == 1
        assert all(r['dry_run'] for r in _rows(qm))

    def test_dry_run_rows_do_not_block_live_actions(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [L(watch=3, days=20, price=100.0)], jobs=[J()],
            settings={'OFFERS_MARKDOWNS_DRY_RUN': 'true'})
        scanner.run_cycle(now=NOW)  # dry observation day

        values = {**BASE_SETTINGS}  # dry_run false again
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda k, d=None: values.get(k, d)
        monkeypatch.setattr('backend.app.core.settings_manager.get_settings_manager',
                            lambda: mock_settings)
        scanner.run_cycle(now=NOW + 86400)
        negotiation.send_offer.assert_called_once()
        trading.revise_fixed_price_item.assert_called_once()


class TestDigest:
    def test_digest_sent_to_owner_chat(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [L(watch=3, days=20)], jobs=[J()],
            settings={'OFFERS_MARKDOWNS_DRY_RUN': 'true',
                      'WHATSAPP_NOTIFY_CHAT_ID': '555'})
        notify = MagicMock(return_value=True)
        monkeypatch.setattr('backend.app.services.whatsapp_notify.notify_whatsapp', notify)
        scanner.run_cycle(now=NOW)
        notify.assert_called_once()
        msg = notify.call_args.args[1]
        assert 'DRY RUN' in msg
        assert '1 offer' in msg and '1 markdown' in msg

    def test_no_actions_no_digest(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [L(watch=0, days=5)], jobs=[J()],
            settings={'WHATSAPP_NOTIFY_CHAT_ID': '555'})
        notify = MagicMock(return_value=True)
        monkeypatch.setattr('backend.app.services.whatsapp_notify.notify_whatsapp', notify)
        scanner.run_cycle(now=NOW)
        notify.assert_not_called()


class TestScheduling:
    def test_seconds_until_next_run_positive_and_within_day(self, tmp_path, monkeypatch):
        scanner, qm, trading, negotiation = make_scanner(
            tmp_path, monkeypatch, [], jobs=[])
        secs = scanner._seconds_until_next_run()
        assert 0 < secs <= 86400


class TestSettingsDefaults:
    def test_autopilot_settings_registered(self):
        from backend.app.core.settings_manager import SettingsManager
        d = SettingsManager.DEFAULTS
        assert d.get('OFFERS_ENABLED') == 'true'
        assert d.get('OFFER_DISCOUNT_PCT') == '10'
        assert d.get('OFFER_MIN_WATCHERS') == '1'
        assert d.get('MARKDOWN_ENABLED') == 'true'
        assert d.get('MARKDOWN_AFTER_DAYS') == '14'
        assert d.get('MARKDOWN_STEP_PCT') == '5'
        assert d.get('MARKDOWN_FLOOR_PCT') == '70'
        assert d.get('OFFERS_MARKDOWNS_DRY_RUN') == 'true'
        assert d.get('AUTOPILOT_RUN_HOUR') == '9'
        assert 'Autopilot' in SettingsManager.SETTING_CATEGORIES
        assert 'OFFERS_MARKDOWNS_DRY_RUN' in SettingsManager.SETTING_CATEGORIES['Autopilot']

    def test_digest_builder(self):
        from backend.app.services.whatsapp_notify import build_autopilot_summary_message
        msg = build_autopilot_summary_message(4, 7, 2, dry_run=True)
        assert 'DRY RUN' in msg
        assert '4 offer' in msg and '7 markdown' in msg and '2 relist' in msg
        live = build_autopilot_summary_message(1, 0, 0, dry_run=False)
        assert 'DRY RUN' not in live
