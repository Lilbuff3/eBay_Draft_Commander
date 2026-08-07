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

    def get_performance(self, queue_manager, days: int = 90,
                        now: Optional[datetime] = None) -> Dict[str, Any]:
        """What's making me money: sell-through rate, days-to-sell, and
        revenue/net/ROI broken down by category and by capture source.

        Listed base = jobs holding a listing_id whose completed_at falls in
        the window; sold = sale rows in the window. Unknown COGS rows count
        toward sell-through/revenue but are excluded from net/ROI."""
        from backend.app.core.database import SaleModel
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        def _category(job) -> str:
            ai = getattr(job, 'ai_data', None) or {}
            ident = ai.get('identification')
            if not isinstance(ident, dict):
                ident = {}
            return (ident.get('category_name') or ident.get('category_id')
                    or ai.get('category_name') or ai.get('category_id')
                    or 'Unknown')

        def _source(job) -> str:
            meta = getattr(job, 'job_metadata', None) or {}
            origin = meta.get('origin') or {}
            if origin.get('channel') == 'whatsapp':
                return 'whatsapp'
            if getattr(job, 'batch_id', None) or \
                    getattr(job, 'source', '') == 'metadata_import':
                return 'books'
            if getattr(job, 'source', '') == 'ebay_import':
                return 'ebay_import'
            return 'web'

        # Listed base: jobs with a listing_id completed inside the window.
        jobs_by_listing: Dict[str, Any] = {}
        jobs_by_id: Dict[str, Any] = {}
        listed_jobs = []
        try:
            for job in queue_manager.get_all_jobs():
                lid = getattr(job, 'listing_id', None)
                if not lid:
                    continue
                jobs_by_listing[str(lid)] = job
                if getattr(job, 'id', None):
                    jobs_by_id[str(job.id)] = job
                completed = _parse_dt(str(getattr(job, 'completed_at', '') or '')) \
                    or _parse_dt(str(getattr(job, 'created_at', '') or ''))
                if completed is not None and completed >= cutoff:
                    listed_jobs.append(job)
        except Exception:
            logger.warning("Performance: job scan failed", exc_info=True)

        session = self.SessionFactory()
        try:
            rows = session.query(SaleModel).all()
        finally:
            session.close()

        def _bucket():
            return {'listed': 0, 'sold': 0, 'revenue': 0.0,
                    'net': 0.0, 'cogs': 0.0, 'days': []}

        by_category: Dict[str, Dict[str, Any]] = {}
        by_source: Dict[str, Dict[str, Any]] = {}
        for job in listed_jobs:
            by_category.setdefault(_category(job), _bucket())['listed'] += 1
            by_source.setdefault(_source(job), _bucket())['listed'] += 1

        sold_count = 0
        all_days: List[float] = []
        for r in rows:
            sold = r.sold_at
            if sold is None:
                continue
            if sold.tzinfo is None:
                sold = sold.replace(tzinfo=timezone.utc)
            if sold < cutoff:
                continue
            job = None
            if r.job_id and str(r.job_id) in jobs_by_id:
                job = jobs_by_id[str(r.job_id)]
            elif r.listing_id and str(r.listing_id) in jobs_by_listing:
                job = jobs_by_listing[str(r.listing_id)]
            sold_count += 1

            net = None
            if r.cogs is not None:
                net = (r.sale_total or 0.0) - (r.fees_est or 0.0) \
                    - (r.ship_est or 0.0) - r.cogs

            days_to_sell = None
            if job is not None:
                listed_at = _parse_dt(str(getattr(job, 'completed_at', '') or '')) \
                    or _parse_dt(str(getattr(job, 'created_at', '') or ''))
                if listed_at is not None:
                    days_to_sell = max(0.0, (sold - listed_at).total_seconds() / 86400)
                    all_days.append(days_to_sell)

            for bucket in (
                by_category.setdefault(_category(job) if job else 'Unknown', _bucket()),
                by_source.setdefault(_source(job) if job else 'web', _bucket()),
            ):
                bucket['sold'] += 1
                bucket['revenue'] += r.sale_total or 0.0
                if net is not None:
                    bucket['net'] += net
                    bucket['cogs'] += r.cogs or 0.0
                if days_to_sell is not None:
                    bucket['days'].append(days_to_sell)

        def _finish(table: Dict[str, Dict[str, Any]], key_name: str) -> List[Dict[str, Any]]:
            out = []
            for key, b in table.items():
                has_net = b['net'] != 0.0 or b['cogs'] > 0
                out.append({
                    key_name: key,
                    'listed': b['listed'],
                    'sold': b['sold'],
                    'sell_through': (round(b['sold'] / b['listed'], 3)
                                     if b['listed'] else None),
                    'revenue': round(b['revenue'], 2),
                    'net': round(b['net'], 2) if has_net else None,
                    'roi': (round(b['net'] / b['cogs'], 2)
                            if b['cogs'] > 0 else None),
                    'avg_days': (round(sum(b['days']) / len(b['days']), 1)
                                 if b['days'] else None),
                })
            out.sort(key=lambda x: x['revenue'], reverse=True)
            return out

        listed_count = len(listed_jobs)
        sorted_days = sorted(all_days)
        median_days = None
        if sorted_days:
            mid = len(sorted_days) // 2
            median_days = (sorted_days[mid] if len(sorted_days) % 2
                           else (sorted_days[mid - 1] + sorted_days[mid]) / 2)
        return {
            'days': days,
            'listed': listed_count,
            'sold': sold_count,
            'sell_through_rate': (round(sold_count / listed_count, 3)
                                  if listed_count else None),
            'avg_days_to_sell': (round(sum(all_days) / len(all_days), 1)
                                 if all_days else None),
            'median_days_to_sell': (round(median_days, 1)
                                    if median_days is not None else None),
            'by_category': _finish(by_category, 'category'),
            'by_source': _finish(by_source, 'source'),
        }

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

    def find_own_sale(self, isbn: Optional[str] = None, mpn: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find the most recent past sale of the exact same ISBN/MPN as a pricing anchor.

        Joins sales → jobs and matches identification.isbn / identification.mpn
        in the job's ai_json. Returns sale_total (what the buyer paid), not list price.
        """
        if not isbn and not mpn:
            return None

        from backend.app.core.database import SaleModel, JobModel
        from sqlalchemy import desc
        import json

        def _sold_at_iso(sold_at):
            if not sold_at:
                return None
            if sold_at.tzinfo is None:
                sold_at = sold_at.replace(tzinfo=timezone.utc)
            return sold_at.isoformat()

        def _match_payload(sale):
            return {
                'price': sale.sale_total,
                'sold_at': _sold_at_iso(sale.sold_at),
                'title': sale.title,
                'order_id': sale.order_id,
            }

        session = self.SessionFactory()
        try:
            rows = (
                session.query(SaleModel, JobModel)
                .join(JobModel, SaleModel.job_id == JobModel.id)
                .order_by(desc(SaleModel.sold_at))
                .all()
            )

            for sale, job in rows:
                if not sale.sale_total:
                    continue

                ai_data = job.ai_data or {}
                if isinstance(ai_data, str):
                    try:
                        ai_data = json.loads(ai_data)
                    except json.JSONDecodeError:
                        ai_data = {}

                ident = ai_data.get('identification', {})
                if not isinstance(ident, dict):
                    continue

                if isbn and ident.get('isbn') == isbn:
                    return _match_payload(sale)
                if mpn and ident.get('mpn') == mpn:
                    return _match_payload(sale)
        except Exception:
            logger.warning("Error finding own sale", exc_info=True)
        finally:
            session.close()

        return None


_ledger: Optional[LedgerService] = None


def get_ledger(db_path) -> LedgerService:
    """Process-wide singleton keyed off first-call db_path (matches how other
    services treat the single commander.db)."""
    global _ledger
    if _ledger is None:
        _ledger = LedgerService(db_path)
    return _ledger
