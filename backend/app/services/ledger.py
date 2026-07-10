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
                try:
                    total = float(order.get('total'))
                except (TypeError, ValueError):
                    total = None
                if not order_id or not total:
                    continue
                job = by_listing.get(str(order.get('legacyItemId') or ''))
                job_cogs = (job.job_metadata or {}).get('cogs') if job else None

                row = session.get(SaleModel, order_id)
                if row is None:
                    est = estimate_net(total, cogs=job_cogs)
                    row = SaleModel(
                        order_id=order_id,
                        listing_id=str(order.get('legacyItemId') or '') or None,
                        job_id=job.id if job else None,
                        title=order.get('itemTitle'),
                        quantity=int(order.get('quantity') or 1),
                        sale_total=total,
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
                    'sold_at': (r.sold_at.replace(tzinfo=timezone.utc).isoformat()
                                if r.sold_at and r.sold_at.tzinfo is None
                                else (r.sold_at.isoformat() if r.sold_at else None)),
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


_ledger: Optional[LedgerService] = None


def get_ledger(db_path) -> LedgerService:
    """Process-wide singleton keyed off first-call db_path (matches how other
    services treat the single commander.db)."""
    global _ledger
    if _ledger is None:
        _ledger = LedgerService(db_path)
    return _ledger
