"""GET /api/today — cheap DB-only aggregate for the home Today panel.

Counts pending reviews, queued jobs, live price-discovery listings, and the
last autopilot cycle (from listing_actions, dry-run rows included — that's
the owner's pre-flip audit view). No eBay calls.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Flask

from backend.app.services.queue_job import JobStatus
from backend.app.services.queue_manager import QueueManager

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc).timestamp()


def _job(job_id, status, listing_id=None, discovery=False):
    meta = {'price_discovery': {'basis': 'markup'}} if discovery else {}
    return SimpleNamespace(id=job_id, status=status, listing_id=listing_id,
                           job_metadata=meta)


def _client(tmp_path, monkeypatch, jobs):
    from backend.app.blueprints.api.today_api import today_bp
    qm = QueueManager(tmp_path / 'base')
    monkeypatch.setattr(qm, 'get_all_jobs', lambda: jobs)
    app = Flask(__name__)
    app.queue_manager = qm
    app.register_blueprint(today_bp, url_prefix='/api')
    return app.test_client(), qm


class TestTodayApi:
    def test_counts(self, tmp_path, monkeypatch):
        jobs = [
            _job('a', JobStatus.PENDING_REVIEW),
            _job('b', JobStatus.PENDING_REVIEW),
            _job('c', JobStatus.PENDING),
            _job('d', JobStatus.COMPLETED, listing_id='100', discovery=True),
            _job('e', JobStatus.SCHEDULED, listing_id='101', discovery=True),
            _job('f', JobStatus.COMPLETED, listing_id='102'),
        ]
        client, qm = _client(tmp_path, monkeypatch, jobs)
        body = client.get('/api/today').get_json()
        assert body['reviews'] == 2
        assert body['queued'] == 1
        assert body['discovery_live'] == 2

    def test_autopilot_last_cycle(self, tmp_path, monkeypatch):
        client, qm = _client(tmp_path, monkeypatch, [])
        from backend.app.services.autopilot_scanner import AutopilotScanner
        scanner = AutopilotScanner(qm)
        # older cycle
        scanner.record_action('1', 'offer', True, {}, NOW - 86400)
        # latest cycle: 2 offers + 1 markdown, dry
        scanner.record_action('2', 'offer', True, {}, NOW)
        scanner.record_action('3', 'offer', True, {}, NOW)
        scanner.record_action('4', 'markdown', True, {}, NOW)

        body = client.get('/api/today').get_json()
        ap = body['autopilot']
        assert ap is not None
        assert ap['dry_run'] is True
        assert ap['offers'] == 2
        assert ap['markdowns'] == 1
        assert ap['relists'] == 0
        assert ap['last_run_at'] == pytest.approx(NOW)

    def test_no_autopilot_history(self, tmp_path, monkeypatch):
        client, qm = _client(tmp_path, monkeypatch, [])
        body = client.get('/api/today').get_json()
        assert body['autopilot'] is None
        assert body['reviews'] == 0
