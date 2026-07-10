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
