"""Ledger performance analytics: sell-through, days-to-sell, category/source ROI.

Seeded tmp DB + fake queue_manager jobs. Answers "what's making me money" so
sourcing can chase the winners.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.app.core.database import SaleModel
from backend.app.services.ledger import LedgerService

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def ledger(tmp_path):
    return LedgerService(tmp_path / 'perf.db')


def _job(job_id, listing_id, days_ago_listed=10, category_id='267',
         category_name=None, channel=None, source='folder', batch_id=None,
         cogs=None):
    ai = {}
    if category_id:
        ai['identification'] = {'category_id': category_id}
    if category_name:
        ai['identification']['category_name'] = category_name
    meta = {}
    if channel:
        meta['origin'] = {'channel': channel, 'chat_id': '111'}
    if cogs is not None:
        meta['cogs'] = cogs
    completed = (NOW - timedelta(days=days_ago_listed)).isoformat()
    return SimpleNamespace(id=job_id, listing_id=listing_id, ai_data=ai,
                           job_metadata=meta, source=source, batch_id=batch_id,
                           completed_at=completed, created_at=completed)


def _sale(ledger, order_id, listing_id, job_id=None, total=50.0,
          days_ago_sold=2, cogs=None):
    session = ledger.SessionFactory()
    try:
        session.add(SaleModel(
            order_id=order_id, listing_id=listing_id, job_id=job_id,
            sale_total=total, fees_est=7.0, ship_est=5.0, cogs=cogs,
            sold_at=(NOW - timedelta(days=days_ago_sold)).replace(tzinfo=None)))
        session.commit()
    finally:
        session.close()


def _qm(jobs):
    qm = MagicMock()
    qm.get_all_jobs.return_value = jobs
    return qm


class TestOverall:
    def test_sell_through_and_counts(self, ledger):
        jobs = [_job(f'j{i}', str(100 + i)) for i in range(4)]
        _sale(ledger, 'o1', '100', job_id='j0')
        _sale(ledger, 'o2', '101', job_id='j1')
        perf = ledger.get_performance(_qm(jobs), days=90, now=NOW)
        assert perf['listed'] == 4
        assert perf['sold'] == 2
        assert perf['sell_through_rate'] == pytest.approx(0.5)

    def test_days_to_sell(self, ledger):
        jobs = [_job('j0', '100', days_ago_listed=10)]
        _sale(ledger, 'o1', '100', job_id='j0', days_ago_sold=2)  # 8 days to sell
        perf = ledger.get_performance(_qm(jobs), days=90, now=NOW)
        assert perf['avg_days_to_sell'] == pytest.approx(8, abs=0.1)
        assert perf['median_days_to_sell'] == pytest.approx(8, abs=0.1)

    def test_old_sales_outside_window_excluded(self, ledger):
        jobs = [_job('j0', '100', days_ago_listed=200)]
        _sale(ledger, 'o1', '100', job_id='j0', days_ago_sold=150)
        perf = ledger.get_performance(_qm(jobs), days=90, now=NOW)
        assert perf['sold'] == 0
        assert perf['listed'] == 0  # listed 200d ago, outside window too

    def test_empty_db(self, ledger):
        perf = ledger.get_performance(_qm([]), days=90, now=NOW)
        assert perf['listed'] == 0 and perf['sold'] == 0
        assert perf['sell_through_rate'] is None
        assert perf['by_category'] == [] and perf['by_source'] == []


class TestByCategory:
    def test_category_breakdown_with_roi(self, ledger):
        jobs = [
            _job('j0', '100', category_id='267', category_name='Books'),
            _job('j1', '101', category_id='267', category_name='Books'),
            _job('j2', '102', category_id='11450', category_name='Clothing'),
        ]
        _sale(ledger, 'o1', '100', job_id='j0', total=50.0, cogs=10.0)
        perf = ledger.get_performance(_qm(jobs), days=90, now=NOW)
        cats = {c['category']: c for c in perf['by_category']}
        books = cats['Books']
        assert books['listed'] == 2
        assert books['sold'] == 1
        assert books['sell_through'] == pytest.approx(0.5)
        assert books['revenue'] == pytest.approx(50.0)
        # net = 50 - 7 - 5 - 10 = 28; roi = 28/10
        assert books['net'] == pytest.approx(28.0)
        assert books['roi'] == pytest.approx(2.8)
        assert cats['Clothing']['sold'] == 0

    def test_unknown_cogs_counts_sold_but_not_roi(self, ledger):
        jobs = [_job('j0', '100', category_name='Books')]
        _sale(ledger, 'o1', '100', job_id='j0', total=50.0, cogs=None)
        perf = ledger.get_performance(_qm(jobs), days=90, now=NOW)
        books = perf['by_category'][0]
        assert books['sold'] == 1
        assert books['net'] is None or books['net'] == 0
        assert books['roi'] is None

    def test_malformed_ai_data_lands_in_unknown(self, ledger):
        job = _job('j0', '100', category_id=None)
        job.ai_data = {'identification': 'not-a-dict'}
        _sale(ledger, 'o1', '100', job_id='j0')
        perf = ledger.get_performance(_qm([job]), days=90, now=NOW)
        assert perf['by_category'][0]['category'] == 'Unknown'


class TestBySource:
    def test_source_breakdown(self, ledger):
        jobs = [
            _job('j0', '100', channel='whatsapp'),
            _job('j1', '101', source='folder'),
            _job('j2', '102', source='metadata_import', batch_id='b1'),
        ]
        _sale(ledger, 'o1', '100', job_id='j0', total=40.0, cogs=5.0)
        perf = ledger.get_performance(_qm(jobs), days=90, now=NOW)
        sources = {s['source']: s for s in perf['by_source']}
        assert sources['whatsapp']['listed'] == 1
        assert sources['whatsapp']['sold'] == 1
        assert sources['books']['listed'] == 1
        assert sources['web']['listed'] == 1


class TestEndpoint:
    def test_performance_route(self, ledger, tmp_path, monkeypatch):
        from flask import Flask
        from backend.app.blueprints.api.ledger_api import ledger_bp

        qm = _qm([_job('j0', '100')])
        qm.db_path = tmp_path / 'perf.db'
        monkeypatch.setattr('backend.app.services.ledger.get_ledger',
                            lambda path: ledger)
        app = Flask(__name__)
        app.queue_manager = qm
        app.register_blueprint(ledger_bp, url_prefix='/api/ledger')
        client = app.test_client()
        resp = client.get('/api/ledger/performance?days=30')
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'sell_through_rate' in body
        assert 'by_category' in body and 'by_source' in body
