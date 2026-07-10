from flask import Blueprint, jsonify, request, current_app
from backend.app.services.ebay_service import eBayService
from backend.app.core.logger import get_logger

analytics_bp = Blueprint('analytics', __name__)
logger = get_logger('api.analytics')
ebay_service = eBayService()


def _attach_thumbnails(orders: list) -> None:
    """Join orders to local jobs by eBay item id so cards can show the photo we listed with."""
    if not orders:
        return
    try:
        from backend.app.blueprints.api.jobs_api import _resolve_thumb_url
        qm = current_app.queue_manager
        by_listing = {j.listing_id: j for j in qm.get_all_jobs() if getattr(j, 'listing_id', None)}
        for order in orders:
            job = by_listing.get(str(order.get('legacyItemId') or ''))
            order['thumbnailUrl'] = _resolve_thumb_url(job, qm) if job else None
    except Exception:
        logger.warning("Thumbnail join for orders failed", exc_info=True)
        for order in orders:
            order.setdefault('thumbnailUrl', None)

@analytics_bp.route('/sales/recent')
def get_recent_sales():
    result, status = ebay_service.get_recent_sales()
    return jsonify(result), status

@analytics_bp.route('/analytics/summary')
def get_analytics_summary():
    try:
        days = int(request.args.get('days', '30'))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid value for days parameter'}), 400
    result, status = ebay_service.get_analytics_summary(days=days)
    return jsonify(result), status

@analytics_bp.route('/analytics/orders')
@analytics_bp.route('/orders')
def get_analytics_orders():
    try:
        days = int(request.args.get('days', '30'))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid value for days parameter'}), 400
    try:
        limit = int(request.args.get('limit', '50'))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid value for limit parameter'}), 400
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
