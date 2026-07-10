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
