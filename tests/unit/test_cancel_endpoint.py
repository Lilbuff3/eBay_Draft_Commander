"""
Tests for the "cancel last" capability:
- eBayService.end_listing(item_id) facade -> delegates to TradingService.end_fixed_price_item
- POST /api/jobs/<job_id>/cancel -> ends eBay listing (if any), then removes the DC job
"""
from unittest.mock import MagicMock

import pytest

from backend.app.services.ebay_service import eBayService


def test_end_listing_delegates_to_trading():
    svc = eBayService()
    svc.trading_service = MagicMock()
    svc.trading_service.end_fixed_price_item.return_value = {'success': True, 'end_time': 'x'}
    out = svc.end_listing('12345')
    svc.trading_service.end_fixed_price_item.assert_called_once_with('12345')
    assert out['success'] is True


from backend.app import create_app
from backend.app.services.queue_manager import QueueManager
import backend.app.blueprints.api.jobs_api as jobs_api


@pytest.fixture
def app(tmp_path):
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    return app


def test_cancel_listed_job_ends_then_removes(app, monkeypatch):
    qm = app.queue_manager
    fake_job = MagicMock(); fake_job.listing_id = '99999'
    monkeypatch.setattr(qm, 'get_job_by_id', lambda jid: fake_job)
    removed = {}
    monkeypatch.setattr(qm, 'remove_job', lambda jid, delete_folder=False: removed.setdefault('id', jid) or True)
    ended = {}
    fake_svc = MagicMock()
    fake_svc.end_listing = lambda iid: (ended.update({'id': iid}) or {'success': True})
    monkeypatch.setattr(jobs_api, 'eBayService', lambda: fake_svc)
    resp = app.test_client().post('/api/jobs/abc123/cancel')
    assert resp.status_code == 200
    assert ended['id'] == '99999'
    assert removed['id'] == 'abc123'


def test_cancel_unlisted_job_just_removes(app, monkeypatch):
    qm = app.queue_manager
    fake_job = MagicMock(); fake_job.listing_id = None
    monkeypatch.setattr(qm, 'get_job_by_id', lambda jid: fake_job)
    removed = {}
    monkeypatch.setattr(qm, 'remove_job', lambda jid, delete_folder=False: removed.setdefault('id', jid) or True)
    resp = app.test_client().post('/api/jobs/xy/cancel')
    assert resp.status_code == 200
    assert removed['id'] == 'xy'


def test_cancel_missing_job_404(app, monkeypatch):
    monkeypatch.setattr(app.queue_manager, 'get_job_by_id', lambda jid: None)
    resp = app.test_client().post('/api/jobs/nope/cancel')
    assert resp.status_code == 404


def test_cancel_ebay_failure_returns_502_and_keeps_job(app, monkeypatch):
    qm = app.queue_manager
    fake_job = MagicMock(); fake_job.listing_id = '777'
    monkeypatch.setattr(qm, 'get_job_by_id', lambda jid: fake_job)
    removed = {}
    monkeypatch.setattr(qm, 'remove_job', lambda jid, delete_folder=False: removed.setdefault('id', jid) or True)
    fake_svc = MagicMock()
    fake_svc.end_listing = lambda iid: {'success': False, 'error': 'eBay says no'}
    monkeypatch.setattr(jobs_api, 'eBayService', lambda: fake_svc)
    resp = app.test_client().post('/api/jobs/zz/cancel')
    assert resp.status_code == 502
    assert 'id' not in removed  # job must NOT be removed when the eBay end fails
