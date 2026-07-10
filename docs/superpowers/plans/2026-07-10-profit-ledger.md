# Profit Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-item profit tracking — COGS captured at listing time (WhatsApp caption / item edit / sourcing flow), sales snapshotted locally from eBay orders, real net profit (sale − fees − shipping − COGS) surfaced in a new Profit tab with weekly P&L.

**Architecture:** New `sales` SQLite table accumulates order snapshots (survives eBay's 90-day order window) via an upsert sweep piggybacked on the existing `/api/orders` fetch. COGS lives in `job_metadata['cogs']` and is frozen onto the sale row at sweep time. A new `LedgerService` owns fee math (reusing the pricing constants sourcing already uses) and summary/item queries. New `ledger_api` blueprint + lazy-loaded React `Profit` tab.

**Tech Stack:** Flask + SQLAlchemy (SQLite WAL), pytest, React 18 + TypeScript + Zustand, existing `apiFetch<T>` client.

**Branch:** work on `feature/profit-ledger` off `master`.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/app/core/database.py` | Modify | Add `SaleModel` (`sales` table) |
| `backend/app/services/ledger.py` | Create | Fee math, sales upsert sweep, summary/items queries, set_cogs |
| `backend/app/blueprints/api/queue_api.py` | Modify | `_extract_cogs` caption parser, wire into `/capture` |
| `backend/app/blueprints/api/jobs_api.py` | Modify | `cogs` field in `/job/<id>/update` and `/jobs/create-from-metadata` |
| `backend/app/blueprints/api/ledger_api.py` | Create | `GET /api/ledger/summary`, `GET /api/ledger/items`, `POST /api/ledger/sales/<id>/cogs` |
| `backend/app/blueprints/api/__init__.py` | Modify | Register `ledger_bp` |
| `backend/app/blueprints/api/analytics_api.py` | Modify | Sweep hook after order fetch |
| `frontend/src/pages/Profit.tsx` | Create | Profit tab UI |
| `frontend/src/App.tsx` | Modify | Lazy import + render branch for `profit` tab |
| `frontend/src/components/Sidebar.tsx` | Modify | Nav item |
| `frontend/src/pages/Sourcing.tsx` | Modify | `sendToBooks` carries paid price as cogs |
| `frontend/src/pages/BatchScan.tsx` | Modify | `BatchItem.cogs`, Draft All payload carries `cogs` |
| `tests/unit/test_ledger.py` | Create | All backend ledger tests |
| `CLAUDE.md` | Modify | Document the pattern |

**Conventions the engineer must know:**
- Python tests: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py -v` (bare `python` may be a broken 3.13).
- Never touch `.env` directly (a PreToolUse hook blocks it).
- `job.job_metadata` is a JSON property over `metadata_json`; setting requires assigning the whole dict back (`job.job_metadata = md`), mutation alone does not persist.
- Services own their DB session via `self.SessionFactory = init_db(db_path)` (see `template_manager.py:39`).
- Frontend must build with `cd frontend && npm run build` before the final commit (project rule).
- Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: `SaleModel` in database.py

**Files:**
- Modify: `backend/app/core/database.py` (after `AppToken`, ~line 138)
- Test: `tests/unit/test_ledger.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_ledger.py`:

```python
"""Profit ledger tests: SaleModel, fee math, sweep, summary, COGS parsing."""
from datetime import datetime, timezone

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py -v`
Expected: FAIL — `ImportError: cannot import name 'SaleModel'`

- [ ] **Step 3: Add the model**

In `backend/app/core/database.py`, after the `AppToken` class:

```python
class SaleModel(Base):
    """Local snapshot of a sold eBay order line — accumulates past eBay's 90-day order window.

    One row per order (v1 records the first line item only, matching the shape
    /api/orders already returns; multi-line orders are rare for this seller).
    cogs is frozen here at sweep time from job_metadata['cogs'] and can be
    filled in later from the Profit tab.
    """
    __tablename__ = 'sales'
    __table_args__ = (
        Index('idx_sales_sold_at', 'sold_at'),
        Index('idx_sales_listing_id', 'listing_id'),
    )

    order_id = Column(String(50), primary_key=True)
    listing_id = Column(String(50))          # eBay legacyItemId — join key to jobs
    job_id = Column(String(10))              # local job id if matched, else NULL
    title = Column(String(255))
    quantity = Column(Integer, default=1)
    sale_total = Column(Float, nullable=False)  # order total (item + any buyer-paid extras)
    sold_at = Column(DateTime)               # order creationDate
    paid_at = Column(DateTime)
    fees_est = Column(Float)                 # FVF% * total + payment fee, frozen at sweep
    ship_est = Column(Float)                 # flat ship estimate, frozen at sweep
    cogs = Column(Float)                     # NULL = unknown, first-class state
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
```

(`Index`, `Float`, `Integer`, `DateTime`, `Column`, `String` are already imported at the top of the file. `datetime`/`timezone` too.)

- [ ] **Step 4: Run test to verify it passes**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py -v`
Expected: 2 PASS. (`init_db` calls `Base.metadata.create_all`, which also auto-creates the new table on the real DB at next boot — no migration needed.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/database.py tests/unit/test_ledger.py
git commit -m "feat(ledger): add sales snapshot table

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: LedgerService — fee math

**Files:**
- Create: `backend/app/services/ledger.py`
- Test: `tests/unit/test_ledger.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_ledger.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py::TestEstimateNet -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.services.ledger'`

- [ ] **Step 3: Create the service with fee math**

Create `backend/app/services/ledger.py`:

```python
"""Profit ledger — local sales snapshots + real net profit math.

Sales rows accumulate in SQLite (past eBay's 90-day order window) via an
upsert sweep piggybacked on every /api/orders fetch. COGS comes from
job_metadata['cogs'] (WhatsApp caption, item edit, or sourcing flow) and is
frozen onto the sale row; unknown COGS is a first-class state (net = None).

Fee estimate reuses the same constants as sourcing.compute_verdict:
    fees = sale_total * FVF_RATE + payment_fee
    net  = sale_total - fees - ship_est - cogs
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.app.core.constants import (
    EBAY_FINAL_VALUE_FEE_RATE,
    EBAY_PAYMENT_PROCESSING_FEE,
)
from backend.app.core.logger import get_logger

logger = get_logger('services.ledger')


def _setting_float(key: str, default: float) -> float:
    from backend.app.core.settings_manager import get_settings_manager
    try:
        return float(get_settings_manager().get(key, str(default)))
    except (TypeError, ValueError):
        return default


def estimate_net(sale_total: float, cogs: Optional[float] = None,
                 ship_cost: Optional[float] = None) -> Dict[str, Any]:
    """Fee/net estimate for one sale. cogs=None -> net=None (unknown, not zero)."""
    if ship_cost is None:
        ship_cost = _setting_float('SOURCING_SHIP_COST', 5.0)
    fees = sale_total * EBAY_FINAL_VALUE_FEE_RATE + EBAY_PAYMENT_PROCESSING_FEE
    net = None
    if cogs is not None:
        net = sale_total - fees - ship_cost - cogs
    return {
        'fees_est': round(fees, 2),
        'ship_est': round(ship_cost, 2),
        'net': round(net, 2) if net is not None else None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ledger.py tests/unit/test_ledger.py
git commit -m "feat(ledger): net profit fee math

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: LedgerService — sales sweep (upsert)

**Files:**
- Modify: `backend/app/services/ledger.py`
- Test: `tests/unit/test_ledger.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_ledger.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py::TestRecordSales -v`
Expected: FAIL — `ImportError: cannot import name 'LedgerService'`

- [ ] **Step 3: Implement LedgerService.record_sales**

Append to `backend/app/services/ledger.py`:

```python
def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """eBay ISO timestamps ('2026-07-08T12:00:00.000Z') -> aware datetime, else None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None


class LedgerService:
    """Owns the sales table. One instance per process (see get_ledger)."""

    def __init__(self, db_path):
        from backend.app.core.database import init_db
        self.db_path = db_path
        self.SessionFactory = init_db(db_path)

    def record_sales(self, orders: List[Dict[str, Any]], queue_manager) -> int:
        """Upsert order snapshots. Freezes fees/ship at first sight; backfills
        cogs from the matched job only while the row's cogs is still NULL
        (a value set via the Profit tab must never be clobbered by a resweep).
        Returns number of rows inserted or updated."""
        from backend.app.core.database import SaleModel
        if not orders:
            return 0

        by_listing = {}
        try:
            by_listing = {
                str(j.listing_id): j
                for j in queue_manager.get_all_jobs()
                if getattr(j, 'listing_id', None)
            }
        except Exception:
            logger.warning("Ledger: job lookup failed, sweeping without COGS join", exc_info=True)

        touched = 0
        session = self.SessionFactory()
        try:
            for order in orders:
                order_id = order.get('orderId')
                total = order.get('total')
                if not order_id or total in (None, 0):
                    continue
                job = by_listing.get(str(order.get('legacyItemId') or ''))
                job_cogs = (job.job_metadata or {}).get('cogs') if job else None

                row = session.get(SaleModel, order_id)
                if row is None:
                    est = estimate_net(float(total), cogs=job_cogs)
                    row = SaleModel(
                        order_id=order_id,
                        listing_id=str(order.get('legacyItemId') or '') or None,
                        job_id=job.id if job else None,
                        title=order.get('itemTitle'),
                        quantity=order.get('quantity') or 1,
                        sale_total=float(total),
                        sold_at=_parse_dt(order.get('creationDate')),
                        paid_at=_parse_dt(order.get('paidDate')),
                        fees_est=est['fees_est'],
                        ship_est=est['ship_est'],
                        cogs=job_cogs,
                    )
                    session.add(row)
                    touched += 1
                elif row.cogs is None and job_cogs is not None:
                    row.cogs = job_cogs
                    if job and not row.job_id:
                        row.job_id = job.id
                    touched += 1
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return touched


_ledger: Optional[LedgerService] = None


def get_ledger(db_path) -> LedgerService:
    """Process-wide singleton keyed off first-call db_path (matches how other
    services treat the single commander.db)."""
    global _ledger
    if _ledger is None:
        _ledger = LedgerService(db_path)
    return _ledger
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ledger.py tests/unit/test_ledger.py
git commit -m "feat(ledger): sales upsert sweep with COGS join

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: LedgerService — summary, items, set_cogs

**Files:**
- Modify: `backend/app/services/ledger.py`
- Test: `tests/unit/test_ledger.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_ledger.py`:

```python
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
```

Also add `timedelta` to the datetime import at the top of the test file:
`from datetime import datetime, timedelta, timezone`

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py::TestSummaryAndItems -v`
Expected: FAIL — `AttributeError: 'LedgerService' object has no attribute 'get_summary'`

- [ ] **Step 3: Implement queries**

Add these methods to `LedgerService` in `backend/app/services/ledger.py`:

```python
    def get_summary(self, weeks: int = 8) -> Dict[str, Any]:
        """Weekly P&L buckets, newest week first. Weeks start Monday (ISO).
        net sums only rows with known COGS; missing_cogs counts the rest."""
        from backend.app.core.database import SaleModel
        now = datetime.now(timezone.utc)
        monday = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
        cutoff = monday - timedelta(weeks=weeks - 1)

        session = self.SessionFactory()
        try:
            rows = (session.query(SaleModel)
                    .filter(SaleModel.sold_at >= cutoff.replace(tzinfo=None))
                    .all())
            buckets: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                sold = r.sold_at
                if sold is None:
                    continue
                if sold.tzinfo is None:
                    sold = sold.replace(tzinfo=timezone.utc)
                week_start = (sold - timedelta(days=sold.weekday())).date().isoformat()
                b = buckets.setdefault(week_start, {
                    'week_start': week_start, 'revenue': 0.0, 'fees': 0.0,
                    'ship': 0.0, 'cogs': 0.0, 'net': 0.0,
                    'sold_count': 0, 'missing_cogs': 0,
                })
                b['revenue'] += r.sale_total or 0.0
                b['fees'] += r.fees_est or 0.0
                b['ship'] += r.ship_est or 0.0
                b['sold_count'] += 1
                if r.cogs is None:
                    b['missing_cogs'] += 1
                else:
                    b['cogs'] += r.cogs
                    b['net'] += (r.sale_total or 0.0) - (r.fees_est or 0.0) \
                        - (r.ship_est or 0.0) - r.cogs
            ordered = sorted(buckets.values(), key=lambda b: b['week_start'], reverse=True)
            for b in ordered:
                for k in ('revenue', 'fees', 'ship', 'cogs', 'net'):
                    b[k] = round(b[k], 2)
            totals = {
                'revenue': round(sum(b['revenue'] for b in ordered), 2),
                'net': round(sum(b['net'] for b in ordered), 2),
                'sold_count': sum(b['sold_count'] for b in ordered),
                'missing_cogs': sum(b['missing_cogs'] for b in ordered),
            }
            return {'weeks': ordered, 'totals': totals}
        finally:
            session.close()

    def get_items(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Sale rows newest first, with per-item net/ROI (None when COGS unknown)."""
        from backend.app.core.database import SaleModel
        session = self.SessionFactory()
        try:
            rows = (session.query(SaleModel)
                    .order_by(SaleModel.sold_at.desc())
                    .limit(limit).all())
            items = []
            for r in rows:
                net = None
                roi = None
                if r.cogs is not None:
                    net = round((r.sale_total or 0.0) - (r.fees_est or 0.0)
                                - (r.ship_est or 0.0) - r.cogs, 2)
                    roi = round(net / r.cogs, 2) if r.cogs > 0 else None
                items.append({
                    'order_id': r.order_id,
                    'listing_id': r.listing_id,
                    'job_id': r.job_id,
                    'title': r.title,
                    'quantity': r.quantity,
                    'sale_total': r.sale_total,
                    'sold_at': r.sold_at.isoformat() if r.sold_at else None,
                    'fees_est': r.fees_est,
                    'ship_est': r.ship_est,
                    'cogs': r.cogs,
                    'net': net,
                    'roi': roi,
                })
            return items
        finally:
            session.close()

    def set_cogs(self, order_id: str, cogs: float) -> bool:
        """Fill/correct COGS on a sale row from the Profit tab. Returns False if unknown order."""
        from backend.app.core.database import SaleModel
        session = self.SessionFactory()
        try:
            row = session.get(SaleModel, order_id)
            if row is None:
                return False
            row.cogs = round(float(cogs), 2)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ledger.py tests/unit/test_ledger.py
git commit -m "feat(ledger): weekly summary, item list, set_cogs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: COGS caption parser + wire into WhatsApp capture

**Files:**
- Modify: `backend/app/blueprints/api/queue_api.py` (parser near `_clean_capture_note` at line 13; wiring in `capture_item` ~line 200 and ~line 265)
- Test: `tests/unit/test_ledger.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_ledger.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py::TestExtractCogs -v`
Expected: FAIL — `ImportError: cannot import name '_extract_cogs'`

- [ ] **Step 3: Implement parser and wire it**

In `backend/app/blueprints/api/queue_api.py`, add near the top (after `_clean_capture_note`, line 17):

```python
import re

# "paid 3", "paid $12.50", "cost 8" — capture COGS from a WhatsApp caption.
# Token is stripped from the note so the cost never reaches the AI prompts
# (a visible "paid 3" would bias Gemini's price estimate low).
_COGS_RE = re.compile(r'\b(?:paid|cost)\s*\$?(\d{1,5}(?:\.\d{1,2})?)\b', re.IGNORECASE)


def _extract_cogs(note: str):
    """Pull a 'paid X' / 'cost X' token out of a capture note.

    Returns (cogs_or_None, note_with_token_removed). No token -> (None, note).
    """
    if not note:
        return None, note or ""
    m = _COGS_RE.search(note)
    if not m:
        return None, note
    cogs = round(float(m.group(1)), 2)
    cleaned = (note[:m.start()] + ' ' + note[m.end():])
    cleaned = ' '.join(cleaned.split()).strip(' ,;-')
    return cogs, cleaned
```

(If `re` is already imported at the top of the file, don't duplicate it — move the `import re` to the existing import block.)

Then in `capture_item`, change line 200 from:

```python
    note = _clean_capture_note(data.get('note'))
```

to:

```python
    note = _clean_capture_note(data.get('note'))
    cogs, note = _extract_cogs(note)
```

And in the metadata block (~line 265), change:

```python
        metadata = {'capture_source': 'hermes'}
        if note:
            metadata['note'] = note
```

to:

```python
        metadata = {'capture_source': 'hermes'}
        if note:
            metadata['note'] = note
        if cogs is not None:
            metadata['cogs'] = cogs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit/test_ledger.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full unit suite (capture path is heavily tested elsewhere)**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit -v`
Expected: no new failures (baseline: 616 passing as of last merge; a pre-existing logging teardown error in queue-manager tests is known noise)

- [ ] **Step 6: Commit**

```bash
git add backend/app/blueprints/api/queue_api.py tests/unit/test_ledger.py
git commit -m "feat(ledger): parse 'paid X' COGS from WhatsApp captions

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: COGS in job update + create-from-metadata

**Files:**
- Modify: `backend/app/blueprints/api/jobs_api.py` (`update_job_metadata` ~line 248; `create_job_from_metadata` ~line 500)

No new unit test file needed — these are two small metadata plumbing branches; the endpoint bodies follow the exact pattern of the adjacent `fulfillmentPolicy`/`ordered_images` branches. Verification is by curl in Step 3.

- [ ] **Step 1: Add `cogs` branch to `update_job_metadata`**

In `backend/app/blueprints/api/jobs_api.py`, inside the `try:` block of `update_job_metadata`, after the `ordered_images` branch (line 247), add:

```python
        if 'cogs' in data:
            metadata = updates.get('job_metadata', job.job_metadata or {})
            raw = data['cogs']
            if raw in (None, ''):
                metadata.pop('cogs', None)
            else:
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    raise ValidationError('cogs must be a number')
                if val < 0 or val > 99999:
                    raise ValidationError('cogs out of range')
                metadata['cogs'] = round(val, 2)
            updates['job_metadata'] = metadata
```

- [ ] **Step 2: Add `cogs` passthrough to `create_job_from_metadata`**

In the same file, in `create_job_from_metadata`, after the `metadata = {...}` dict is built (line 500), alongside the `condition`/`user_approved` lines, add:

```python
        cogs_raw = data.get('cogs')
        if cogs_raw not in (None, ''):
            try:
                metadata['cogs'] = round(float(cogs_raw), 2)
            except (TypeError, ValueError):
                pass  # bad cogs never blocks a draft
```

- [ ] **Step 3: Verify by hand against the running backend**

Backend must be running (`python backend/run_service.py` or already up on port 5000). Pick any existing job id from `GET /api/jobs`, then:

```bash
curl -s -X POST http://127.0.0.1:5000/api/job/<job_id>/update \
  -H "Content-Type: application/json" -d '{"cogs": 4.5}'
curl -s http://127.0.0.1:5000/api/jobs | grep -o '"cogs": 4.5'
```

Expected: update returns success JSON; the jobs payload contains `"cogs": 4.5` in that job's metadata. Then clear it: `-d '{"cogs": null}'` and confirm removal. (If backend not running, defer this check to Task 8 Step 4 which requires it anyway.)

- [ ] **Step 4: Commit**

```bash
git add backend/app/blueprints/api/jobs_api.py
git commit -m "feat(ledger): cogs field on job update and metadata import

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Ledger API blueprint

**Files:**
- Create: `backend/app/blueprints/api/ledger_api.py`
- Modify: `backend/app/blueprints/api/__init__.py`

- [ ] **Step 1: Create the blueprint**

Create `backend/app/blueprints/api/ledger_api.py`:

```python
"""Profit ledger endpoints: weekly P&L summary, sold-item list, COGS fill-in.

All reads come from the local sales snapshot table (populated by the sweep in
analytics_api on every /api/orders fetch) — no live eBay calls here.
"""
from flask import Blueprint, jsonify, request, current_app

from backend.app.core.logger import get_logger
from backend.app.blueprints.api.helpers import error_response

ledger_bp = Blueprint('ledger', __name__)
logger = get_logger('api.ledger')


def _ledger():
    from backend.app.services.ledger import get_ledger
    return get_ledger(current_app.queue_manager.db_path)


@ledger_bp.route('/summary')
def ledger_summary():
    try:
        weeks = int(request.args.get('weeks', '8'))
    except (ValueError, TypeError):
        return error_response('Invalid value for weeks parameter', 400)
    weeks = max(1, min(weeks, 52))
    return jsonify(_ledger().get_summary(weeks=weeks))


@ledger_bp.route('/items')
def ledger_items():
    try:
        limit = int(request.args.get('limit', '200'))
    except (ValueError, TypeError):
        return error_response('Invalid value for limit parameter', 400)
    items = _ledger().get_items(limit=max(1, min(limit, 500)))

    # Enrich with thumbnails + days_to_sell via the local job, same join
    # analytics_api uses for orders.
    try:
        from backend.app.blueprints.api.jobs_api import _resolve_thumb_url
        from datetime import datetime
        qm = current_app.queue_manager
        for item in items:
            item['thumbnailUrl'] = None
            item['days_to_sell'] = None
            job = qm.get_job_by_id(item['job_id']) if item.get('job_id') else None
            if not job:
                continue
            item['thumbnailUrl'] = _resolve_thumb_url(job, qm)
            try:
                created = datetime.fromisoformat(job.created_at)
                sold = datetime.fromisoformat(item['sold_at']) if item['sold_at'] else None
                if sold:
                    if created.tzinfo is None and sold.tzinfo is not None:
                        created = created.replace(tzinfo=sold.tzinfo)
                    item['days_to_sell'] = max(0, (sold - created).days)
            except (TypeError, ValueError):
                pass
    except Exception:
        logger.warning("Ledger item enrichment failed", exc_info=True)

    return jsonify({'items': items})


@ledger_bp.route('/sales/<order_id>/cogs', methods=['POST'])
def ledger_set_cogs(order_id):
    data = request.json or {}
    raw = data.get('cogs')
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return error_response('cogs must be a number', 400)
    if val < 0 or val > 99999:
        return error_response('cogs out of range', 400)
    if not _ledger().set_cogs(order_id, val):
        return error_response('Sale not found', 404)
    return jsonify({'success': True, 'order_id': order_id, 'cogs': round(val, 2)})
```

**Check before using:** confirm `QueueManager` exposes `db_path` — `Grep "self.db_path" backend/app/services/queue_manager.py`. It is set in `__init__` (used at line 49: `init_db(self.db_path)`). Also confirm `helpers.py` exports `error_response` (every other api module imports it the same way — copy their exact import line if it differs).

- [ ] **Step 2: Register the blueprint**

In `backend/app/blueprints/api/__init__.py`, add to the imports (line 12 area):

```python
from .ledger_api import ledger_bp
```

and to the registrations (line 25 area):

```python
api_bp.register_blueprint(ledger_bp, url_prefix='/ledger')
```

- [ ] **Step 3: Verify app still boots + routes exist**

```bash
"C:\Program Files\Python312\python.exe" -c "from backend.app import create_app; app = create_app(); print([str(r) for r in app.url_map.iter_rules() if 'ledger' in str(r)])"
```

Expected: prints `/api/ledger/summary`, `/api/ledger/items`, `/api/ledger/sales/<order_id>/cogs`. (If `create_app` needs args, mirror how `wsgi.py` calls it.)

- [ ] **Step 4: Commit**

```bash
git add backend/app/blueprints/api/ledger_api.py backend/app/blueprints/api/__init__.py
git commit -m "feat(ledger): /api/ledger summary, items, cogs endpoints

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Sweep hook on orders fetch

**Files:**
- Modify: `backend/app/blueprints/api/analytics_api.py:51-54`

- [ ] **Step 1: Add the sweep**

In `get_analytics_orders`, after the `_attach_thumbnails` call, change:

```python
    result, status = ebay_service.get_recent_orders(days=days, limit=limit)
    if status == 200:
        _attach_thumbnails(result.get('orders', []))
    return jsonify(result), status
```

to:

```python
    result, status = ebay_service.get_recent_orders(days=days, limit=limit)
    if status == 200:
        _attach_thumbnails(result.get('orders', []))
        # Profit ledger: snapshot sold orders locally (survives eBay's 90-day
        # order window). Best-effort — a ledger failure never breaks Orders.
        try:
            from backend.app.services.ledger import get_ledger
            get_ledger(current_app.queue_manager.db_path).record_sales(
                result.get('orders', []), current_app.queue_manager)
        except Exception:
            logger.warning("Ledger sales sweep failed", exc_info=True)
    return jsonify(result), status
```

- [ ] **Step 2: Run full unit suite**

Run: `"C:\Program Files\Python312\python.exe" -m pytest tests/unit -v`
Expected: no new failures

- [ ] **Step 3: Restart backend and verify live sweep**

Restart backend (`POST /api/system/restart` if supervised, else manual). Then:

```bash
curl -s "http://127.0.0.1:5000/api/orders?days=30" > /dev/null
curl -s "http://127.0.0.1:5000/api/ledger/summary?weeks=8"
curl -s "http://127.0.0.1:5000/api/ledger/items?limit=5"
```

Expected: summary returns real weekly buckets with `sold_count` matching recent eBay orders; items returns rows (COGS mostly null — expected, old inventory has no cost data).

- [ ] **Step 4: Commit**

```bash
git add backend/app/blueprints/api/analytics_api.py
git commit -m "feat(ledger): snapshot sales on every orders fetch

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Frontend — Profit tab

**Files:**
- Create: `frontend/src/pages/Profit.tsx`
- Modify: `frontend/src/App.tsx` (lazy import list ~line 27, render branches ~line 195)
- Modify: `frontend/src/components/Sidebar.tsx:9-19`

- [ ] **Step 1: Create the page**

Create `frontend/src/pages/Profit.tsx`:

```tsx
import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, Wallet } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { cn } from '@/lib/utils'

interface LedgerWeek {
    week_start: string
    revenue: number
    fees: number
    ship: number
    cogs: number
    net: number
    sold_count: number
    missing_cogs: number
}

interface LedgerSummary {
    weeks: LedgerWeek[]
    totals: { revenue: number; net: number; sold_count: number; missing_cogs: number }
}

interface LedgerItem {
    order_id: string
    title: string | null
    sale_total: number
    sold_at: string | null
    fees_est: number | null
    ship_est: number | null
    cogs: number | null
    net: number | null
    roi: number | null
    days_to_sell: number | null
    thumbnailUrl: string | null
}

const money = (n: number | null | undefined) =>
    n === null || n === undefined ? '—' : `$${n.toFixed(2)}`

function WeekCard({ week, label }: { week: LedgerWeek | undefined; label: string }) {
    return (
        <div className="rounded-2xl bg-white/5 border border-white/10 p-4">
            <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">{label}</div>
            <div className={cn('text-2xl font-bold',
                (week?.net ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                {money(week?.net ?? 0)}
            </div>
            <div className="text-xs text-slate-400 mt-1">
                {week ? `${week.sold_count} sold · ${money(week.revenue)} gross` : 'no sales'}
            </div>
            {week && week.missing_cogs > 0 && (
                <div className="text-xs text-amber-400 mt-1">
                    {week.missing_cogs} missing cost — net understated
                </div>
            )}
        </div>
    )
}

function CogsCell({ item, onSaved }: { item: LedgerItem; onSaved: () => void }) {
    const [editing, setEditing] = useState(false)
    const [value, setValue] = useState('')
    const save = async () => {
        const v = parseFloat(value)
        if (isNaN(v) || v < 0) { setEditing(false); return }
        try {
            await apiFetch(`/api/ledger/sales/${item.order_id}/cogs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cogs: v }),
            })
            onSaved()
        } finally {
            setEditing(false)
        }
    }
    if (item.cogs !== null && !editing) {
        return (
            <button className="text-slate-300 hover:text-white" onClick={() => { setValue(String(item.cogs)); setEditing(true) }}>
                {money(item.cogs)}
            </button>
        )
    }
    if (!editing) {
        return (
            <button className="text-amber-400 underline decoration-dotted" onClick={() => setEditing(true)}>
                add cost
            </button>
        )
    }
    return (
        <input
            autoFocus
            inputMode="decimal"
            className="w-16 rounded bg-white/10 border border-white/20 px-1 py-0.5 text-right text-white"
            value={value}
            onChange={e => setValue(e.target.value)}
            onBlur={save}
            onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
        />
    )
}

export function Profit() {
    const [summary, setSummary] = useState<LedgerSummary | null>(null)
    const [items, setItems] = useState<LedgerItem[]>([])
    const [loading, setLoading] = useState(false)

    const load = useCallback(async () => {
        setLoading(true)
        try {
            // Fetch orders first so the sweep runs and the ledger is fresh
            await apiFetch('/api/orders?days=30').catch(() => null)
            const [s, i] = await Promise.all([
                apiFetch<LedgerSummary>('/api/ledger/summary?weeks=8'),
                apiFetch<{ items: LedgerItem[] }>('/api/ledger/items?limit=200'),
            ])
            setSummary(s)
            setItems(i.items)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { void load() }, [load])

    const missing = summary?.totals.missing_cogs ?? 0

    return (
        <div className="h-full overflow-auto p-4 md:p-6">
            <div className="mx-auto max-w-3xl space-y-4 pb-24">
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <h1 className="text-2xl font-display font-bold text-white tracking-tight flex items-center gap-2">
                            <Wallet size={22} /> Profit
                        </h1>
                        <p className="text-slate-400 text-sm">Real net after fees, shipping and cost of goods</p>
                    </div>
                    <button
                        onClick={() => void load()}
                        className="rounded-xl bg-white/10 border border-white/10 p-2 text-slate-300 hover:text-white"
                        aria-label="Refresh"
                    >
                        <RefreshCw size={16} className={cn(loading && 'animate-spin')} />
                    </button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                    <WeekCard week={summary?.weeks[0]} label="This week" />
                    <WeekCard week={summary?.weeks[1]} label="Last week" />
                </div>

                {missing > 0 && (
                    <div className="rounded-xl bg-amber-500/10 border border-amber-500/30 px-3 py-2 text-sm text-amber-300">
                        {missing} sold item{missing !== 1 ? 's' : ''} missing cost — tap “add cost” below to fix your numbers
                    </div>
                )}

                <div className="space-y-2">
                    {items.map(item => (
                        <div key={item.order_id} className="rounded-2xl bg-white/5 border border-white/10 p-3 flex items-center gap-3">
                            {item.thumbnailUrl
                                ? <img src={item.thumbnailUrl} alt="" className="w-12 h-12 rounded-lg object-cover shrink-0" />
                                : <div className="w-12 h-12 rounded-lg bg-white/10 shrink-0" />}
                            <div className="min-w-0 flex-1">
                                <div className="text-sm text-white truncate">{item.title || item.order_id}</div>
                                <div className="text-xs text-slate-400">
                                    {money(item.sale_total)} sale
                                    {item.days_to_sell !== null && ` · ${item.days_to_sell}d to sell`}
                                    {item.roi !== null && ` · ${Math.round(item.roi * 100)}% ROI`}
                                </div>
                            </div>
                            <div className="text-right shrink-0">
                                <div className={cn('text-sm font-semibold',
                                    item.net === null ? 'text-slate-500'
                                        : item.net >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                                    {item.net === null ? 'net ?' : money(item.net)}
                                </div>
                                <div className="text-xs">
                                    <CogsCell item={item} onSaved={() => void load()} />
                                </div>
                            </div>
                        </div>
                    ))}
                    {!loading && items.length === 0 && (
                        <div className="text-center text-slate-500 text-sm py-10">
                            No sales recorded yet — sales appear after your next order sync
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
```

**Check before using:** confirm `apiFetch`'s exact signature in `frontend/src/lib/api.ts` (generic + RequestInit options). If POST calls in this codebase go through a helper like `apiFetch(path, { method, body })` without explicit headers (the wrapper may set Content-Type itself), match the existing call style — copy how `ReviewQueue.tsx` or `Sourcing.tsx` POSTs.

- [ ] **Step 2: Wire tab into App.tsx**

Add to the lazy imports (after line 27):

```tsx
const Profit = lazy(() => import('@/pages/Profit').then(m => ({ default: m.Profit })))
```

Add a render branch next to the others (after `{activeTab === 'orders' && <Orders />}` line 194):

```tsx
              {activeTab === 'profit' && <Profit />}
```

- [ ] **Step 3: Add sidebar nav item**

In `frontend/src/components/Sidebar.tsx`: add `Wallet` to the lucide import on line 1, and insert into the Workspace group after the `orders` item (line 14):

```tsx
            { id: 'profit', icon: Wallet, label: 'Profit' },
```

(Mobile nav stays unchanged — nav bar is full; Profit is reachable from the sidebar/desktop, and mobile users can be added later if wanted.)

- [ ] **Step 4: Typecheck + build**

```bash
cd frontend && npm run build
```

Expected: build succeeds; a new `Profit-*.js` chunk appears in `../static/app/assets/` (lazy split intact — Profit must NOT be statically imported anywhere eager).

- [ ] **Step 5: Verify in browser**

Backend on 5000, then `cd frontend && npm run dev`, open `http://localhost:5175`, click Profit in sidebar. Expected: week cards render, item rows show recent sales, "add cost" saves and net recomputes on reload.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Profit.tsx frontend/src/App.tsx frontend/src/components/Sidebar.tsx static/app
git commit -m "feat(ledger): Profit tab with weekly P&L and COGS fill-in

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Sourcing → Books COGS flow-through

**Files:**
- Modify: `frontend/src/pages/Sourcing.tsx:314-337` (`sendToBooks`)
- Modify: `frontend/src/pages/BatchScan.tsx` (`BatchItem` interface line 42; Draft All payload ~line 342)

- [ ] **Step 1: Carry paid price out of Sourcing**

In `Sourcing.tsx` `sendToBooks`, the pushed object (line 320) gains one field — after `price: ...`:

```tsx
                cogs: row.paid || '',
```

(`row.paid` already exists on `SourcingRow` — it's what the Bought/paid tracking stores; see `totalPaid` reduce at line 340.)

- [ ] **Step 2: Accept + forward in BatchScan**

In `BatchScan.tsx`:
1. Add to `interface BatchItem` (line 42): `cogs?: string`
2. In the Draft All payload object (~line 342, next to `price: item.price || undefined`), add:

```tsx
                    cogs: item.cogs && parseFloat(item.cogs) > 0 ? parseFloat(item.cogs) : undefined,
```

(The backend side already accepts `cogs` — Task 6 Step 2.)

- [ ] **Step 3: Build**

```bash
cd frontend && npm run build
```

Expected: success.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Sourcing.tsx frontend/src/pages/BatchScan.tsx static/app
git commit -m "feat(ledger): sourcing paid price rides into book drafts as COGS

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: Docs + final verification + merge prep

**Files:**
- Modify: `CLAUDE.md` (Key Patterns section + Database section)

- [ ] **Step 1: Document the pattern in CLAUDE.md**

Add to **Key Patterns** (after the WhatsApp pause bullet):

```markdown
- **Profit ledger (Profit tab)** — real net per sale: `sales` table (SaleModel) snapshots eBay orders locally on every `/api/orders` fetch (`ledger.record_sales`, best-effort hook in `analytics_api`) so history outlives eBay's 90-day window. COGS = `job_metadata['cogs']`, captured three ways: WhatsApp caption token `paid X`/`cost X` (parsed by `_extract_cogs` in `queue_api.py` and **stripped from the note** so it never biases Gemini pricing), `cogs` field on `/api/job/<id>/update`, and Sourcing→Books flow-through (`cogs` in create-from-metadata payload). Frozen onto the sale row at sweep; resweeps backfill NULL cogs but never overwrite. `net = sale_total − FVF − $0.30 − SOURCING_SHIP_COST − cogs`; unknown COGS ⇒ `net: null` (first-class, amber "add cost" fill-in on the Profit tab writes via `POST /api/ledger/sales/<order_id>/cogs`). Endpoints: `/api/ledger/summary?weeks=N` (Monday-start weekly buckets), `/api/ledger/items`. Frontend `pages/Profit.tsx`, tab `profit`, desktop sidebar only.
```

Add to **Database** table list:

```markdown
- **`sales`** table (SaleModel) — local sold-order snapshots for the profit ledger: order_id PK, listing_id/job_id join keys, sale_total, sold_at, frozen fees_est/ship_est/cogs
```

- [ ] **Step 2: Full test suite**

```bash
"C:\Program Files\Python312\python.exe" -m pytest tests/unit -v
cd frontend && npm run test -- --run
```

Expected: backend all green (plus new ledger tests), frontend Vitest green.

- [ ] **Step 3: Commit docs**

```bash
git add CLAUDE.md
git commit -m "docs: document profit ledger pattern

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Finish branch**

Use superpowers:finishing-a-development-branch — merge `feature/profit-ledger` to `master`, push, restart backend (`POST /api/system/restart`) so the new table and routes go live.

---

## Out of Scope (deliberate, do not build)

- **v2 auto-offers to watchers** (`ebay/negotiation.py`) — separate plan after ledger proves out.
- **Actual fees via Finances API** — needs a new OAuth scope + manual re-consent; estimate is fine for v1.
- **Per-line-item rows for multi-line orders** — v1 stores first line item per order (matches existing `/api/orders` shape).
- **Mobile nav slot for Profit** — sidebar only for now.
- **COGS input inside the item-detail card** — the backend accepts `cogs` on `/api/job/<id>/update` (Task 6), but no pre-sale edit UI ships in v1. Caption capture + sourcing flow cover entry; the Profit tab's "add cost" covers correction after sale. Wiring an input into `components/item-detail/` is a small follow-up once ledger proves out.
- **Backfilling COGS for legacy/pre-tool sales** — they land in the missing-cost bucket by design.
