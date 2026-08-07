"""Profit ledger tests: SaleModel, fee math, sweep, summary, COGS parsing."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.database import init_db, SaleModel


@pytest.fixture
def session_factory(tmp_path):
    return init_db(tmp_path / "test_ledger.db")


class TestSaleModel:
    def test_sale_row_roundtrip(self, session_factory):
        session = session_factory()
        try:
            sale = SaleModel(
                order_id="12-34567-89012",
                listing_id="256789012345",
                job_id="a1b2c3d4",
                title="Aiwa CSD-ES227 Boombox",
                quantity=1,
                sale_total=54.99,
                sold_at=datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc),
                fees_est=7.58,
                ship_est=5.00,
                cogs=8.00,
            )
            session.add(sale)
            session.commit()

            row = session.query(SaleModel).one()
            assert row.order_id == "12-34567-89012"
            assert row.sale_total == 54.99
            assert row.cogs == 8.00
            assert row.created_at is not None
        finally:
            session.close()

    def test_cogs_nullable(self, session_factory):
        session = session_factory()
        try:
            session.add(SaleModel(order_id="x-1", sale_total=10.0))
            session.commit()
            assert session.query(SaleModel).one().cogs is None
        finally:
            session.close()


from backend.app.services.ledger import estimate_net


class TestEstimateNet:
    def test_full_math(self):
        # 54.99 sale, $8 cogs, $5 ship: fees = 54.99*0.1325 + 0.30 = 7.5862
        result = estimate_net(54.99, cogs=8.00, ship_cost=5.00)
        assert result['fees_est'] == 7.59
        assert result['ship_est'] == 5.00
        # net = 54.99 - 7.5862 - 5 - 8 = 34.40 (rounded)
        assert result['net'] == 34.40

    def test_unknown_cogs_gives_null_net(self):
        result = estimate_net(20.00, cogs=None, ship_cost=5.00)
        assert result['net'] is None
        assert result['fees_est'] == 2.95  # 20*0.1325 + 0.30

    def test_ship_cost_defaults_from_settings(self):
        # explicit ship_cost=None falls back to SOURCING_SHIP_COST (default 5.0)
        result = estimate_net(20.00, cogs=1.00)
        assert result['ship_est'] == 5.00


from backend.app.services.ledger import LedgerService


class FakeJob:
    def __init__(self, job_id, listing_id, cogs=None, created_at="2026-06-20T10:00:00+00:00"):
        self.id = job_id
        self.listing_id = listing_id
        self.job_metadata = {'cogs': cogs} if cogs is not None else {}
        self.created_at = created_at


class FakeQM:
    def __init__(self, jobs):
        self._jobs = jobs

    def get_all_jobs(self):
        return self._jobs


ORDER = {
    'orderId': '12-34567-89012',
    'creationDate': '2026-07-08T12:00:00.000Z',
    'total': 54.99,
    'status': 'NOT_STARTED',
    'itemTitle': 'Aiwa CSD-ES227 Boombox',
    'legacyItemId': '256789012345',
    'quantity': 1,
    'paidDate': '2026-07-08T12:05:00.000Z',
}


class TestRecordSales:
    def _svc(self, tmp_path):
        return LedgerService(tmp_path / "ledger.db")

    def test_records_order_with_job_cogs(self, tmp_path):
        svc = self._svc(tmp_path)
        qm = FakeQM([FakeJob('a1b2c3d4', '256789012345', cogs=8.00)])
        count = svc.record_sales([ORDER], qm)
        assert count == 1
        session = svc.SessionFactory()
        try:
            row = session.query(SaleModel).one()
            assert row.order_id == '12-34567-89012'
            assert row.job_id == 'a1b2c3d4'
            assert row.cogs == 8.00
            assert row.sale_total == 54.99
            assert row.fees_est is not None
            assert row.sold_at.year == 2026
        finally:
            session.close()

    def test_upsert_is_idempotent(self, tmp_path):
        svc = self._svc(tmp_path)
        qm = FakeQM([])
        svc.record_sales([ORDER], qm)
        svc.record_sales([ORDER], qm)
        session = svc.SessionFactory()
        try:
            assert session.query(SaleModel).count() == 1
        finally:
            session.close()

    def test_resweep_backfills_cogs_but_never_overwrites(self, tmp_path):
        svc = self._svc(tmp_path)
        # first sweep: no job match -> cogs NULL
        svc.record_sales([ORDER], FakeQM([]))
        # user later fills COGS on the job; resweep backfills
        svc.record_sales([ORDER], FakeQM([FakeJob('a1b2c3d4', '256789012345', cogs=3.50)]))
        session = svc.SessionFactory()
        try:
            assert session.query(SaleModel).one().cogs == 3.50
        finally:
            session.close()
        # a different job cogs on a THIRD sweep must NOT overwrite the stored 3.50
        svc.record_sales([ORDER], FakeQM([FakeJob('a1b2c3d4', '256789012345', cogs=99.0)]))
        session = svc.SessionFactory()
        try:
            assert session.query(SaleModel).one().cogs == 3.50
        finally:
            session.close()

    def test_skips_orders_without_id_or_total(self, tmp_path):
        svc = self._svc(tmp_path)
        bad = [{'orderId': None, 'total': 5.0}, {'orderId': 'x-2', 'total': None}]
        assert svc.record_sales(bad, FakeQM([])) == 0

    def test_malformed_total_skipped_not_crash(self, tmp_path):
        svc = self._svc(tmp_path)
        bad = [
            {**ORDER, 'orderId': 'bad-1', 'total': {'value': '5.00'}},  # dict junk
            {**ORDER, 'orderId': 'bad-2', 'total': 0},                   # zero
            {**ORDER, 'orderId': 'good-1'},                              # valid 54.99
        ]
        assert svc.record_sales(bad, FakeQM([])) == 1

    def test_sold_at_serialized_as_utc(self, tmp_path):
        svc = self._svc(tmp_path)
        svc.record_sales([ORDER], FakeQM([]))
        items = svc.get_items(limit=1)
        assert items[0]['sold_at'].endswith('+00:00')


def _seed(svc, order_id, total, cogs, sold_at):
    session = svc.SessionFactory()
    try:
        from backend.app.services.ledger import estimate_net
        est = estimate_net(total, cogs=cogs, ship_cost=5.0)
        session.add(SaleModel(
            order_id=order_id, sale_total=total, cogs=cogs,
            sold_at=sold_at, fees_est=est['fees_est'], ship_est=5.0,
            title=f"Item {order_id}", listing_id=f"L{order_id}",
        ))
        session.commit()
    finally:
        session.close()


class TestSummaryAndItems:
    def test_summary_buckets_by_week(self, tmp_path):
        svc = LedgerService(tmp_path / "ledger.db")
        now = datetime.now(timezone.utc)
        _seed(svc, 'w0-a', 50.0, 10.0, now)
        _seed(svc, 'w0-b', 20.0, None, now)          # missing cogs
        _seed(svc, 'w1-a', 30.0, 5.0, now - timedelta(days=8))
        result = svc.get_summary(weeks=4)
        assert len(result['weeks']) <= 4
        this_week = result['weeks'][0]
        assert this_week['sold_count'] == 2
        assert this_week['revenue'] == 70.0
        assert this_week['missing_cogs'] == 1
        # net only sums rows with known cogs
        assert this_week['net'] is not None
        assert result['totals']['sold_count'] == 3

    def test_items_ordered_newest_first(self, tmp_path):
        svc = LedgerService(tmp_path / "ledger.db")
        now = datetime.now(timezone.utc)
        _seed(svc, 'old', 10.0, 1.0, now - timedelta(days=5))
        _seed(svc, 'new', 20.0, None, now)
        items = svc.get_items(limit=10)
        assert items[0]['order_id'] == 'new'
        assert items[0]['net'] is None                # unknown cogs -> null net
        assert items[1]['net'] is not None
        assert items[1]['roi'] is not None

    def test_set_cogs_updates_row(self, tmp_path):
        svc = LedgerService(tmp_path / "ledger.db")
        _seed(svc, 'x-1', 25.0, None, datetime.now(timezone.utc))
        assert svc.set_cogs('x-1', 4.0) is True
        items = svc.get_items(limit=1)
        assert items[0]['cogs'] == 4.0
        assert items[0]['net'] is not None
        assert svc.set_cogs('nope', 4.0) is False


from backend.app.core.database import JobModel
from backend.app.services.ledger import LedgerService


class TestFindOwnSale:
    def _seed_job_and_sale(self, session_factory, job_id, isbn=None, mpn=None,
                           sale_total=30.0, order_id="ord-1"):
        session = session_factory()
        try:
            ident = {}
            if isbn:
                ident["isbn"] = isbn
            if mpn:
                ident["mpn"] = mpn
            job = JobModel(
                id=job_id,
                folder_path=f"/tmp/{job_id}",
                folder_name=job_id,
                status="completed",
            )
            job.ai_data = {"identification": ident}
            session.add(job)
            session.add(SaleModel(
                order_id=order_id,
                listing_id=f"list-{job_id}",
                job_id=job_id,
                title="Test Item",
                sale_total=sale_total,
                sold_at=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
            ))
            session.commit()
        finally:
            session.close()

    def test_matches_isbn(self, session_factory, tmp_path):
        self._seed_job_and_sale(session_factory, "jobisbn01", isbn="9780000000001", sale_total=44.0)
        svc = LedgerService(tmp_path / "test_ledger.db")
        # Point the service at the same SessionFactory the fixture created
        svc.SessionFactory = session_factory
        hit = svc.find_own_sale(isbn="9780000000001")
        assert hit is not None
        assert hit["price"] == 44.0
        assert hit["order_id"] == "ord-1"
        assert hit["sold_at"] is not None

    def test_matches_mpn(self, session_factory, tmp_path):
        self._seed_job_and_sale(session_factory, "jobmpn001", mpn="XYZ-9", sale_total=19.5, order_id="ord-m")
        svc = LedgerService(tmp_path / "test_ledger.db")
        svc.SessionFactory = session_factory
        hit = svc.find_own_sale(mpn="XYZ-9")
        assert hit is not None
        assert hit["price"] == 19.5

    def test_no_match_returns_none(self, session_factory, tmp_path):
        self._seed_job_and_sale(session_factory, "jobother1", isbn="9781111111111")
        svc = LedgerService(tmp_path / "test_ledger.db")
        svc.SessionFactory = session_factory
        assert svc.find_own_sale(isbn="9789999999999") is None

    def test_empty_args_returns_none(self, session_factory, tmp_path):
        svc = LedgerService(tmp_path / "test_ledger.db")
        svc.SessionFactory = session_factory
        assert svc.find_own_sale() is None
        assert svc.find_own_sale(isbn=None, mpn=None) is None


from backend.app.blueprints.api.queue_api import _extract_cogs


class TestExtractCogs:
    def test_paid_token(self):
        cogs, note = _extract_cogs("vintage boombox paid 3 works great")
        assert cogs == 3.0
        assert note == "vintage boombox works great"

    def test_dollar_sign_and_decimals(self):
        cogs, note = _extract_cogs("paid $12.50")
        assert cogs == 12.50
        assert note == ""

    def test_cost_synonym(self):
        cogs, note = _extract_cogs("cost 8, tested working")
        assert cogs == 8.0
        assert note == "tested working"

    def test_no_token_passthrough(self):
        cogs, note = _extract_cogs("mint condition sealed")
        assert cogs is None
        assert note == "mint condition sealed"

    def test_paid_without_number_not_matched(self):
        # "paid full price" must not eat the word or invent a cogs
        cogs, note = _extract_cogs("buyer paid full price last time")
        assert cogs is None
        assert note == "buyer paid full price last time"

    def test_empty(self):
        assert _extract_cogs("") == (None, "")
