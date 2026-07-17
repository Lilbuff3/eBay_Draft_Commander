"""GET /api/today — the home Today panel's one cheap aggregate.

DB-only (no eBay calls): pending-review count, queued count, live
price-discovery listings, and the last autopilot cycle summarized from
listing_actions (dry-run rows included — that's the pre-flip audit view).
Ship-due counts come from the existing OrderStats fetch on the frontend.
"""
from flask import Blueprint, jsonify, current_app

from backend.app.core.logger import get_logger
from backend.app.services.queue_job import JobStatus

today_bp = Blueprint('today', __name__)
logger = get_logger('api.today')


def _status_value(job):
    status = getattr(job, 'status', None)
    return getattr(status, 'value', status)


@today_bp.route('/today')
def today():
    qm = getattr(current_app, 'queue_manager', None)
    if not qm:
        return jsonify({'error': 'Queue manager not initialized'}), 500

    reviews = queued = discovery_live = 0
    try:
        for job in qm.get_all_jobs():
            status = _status_value(job)
            if status == JobStatus.PENDING_REVIEW.value:
                reviews += 1
            elif status == JobStatus.PENDING.value:
                queued += 1
            if (getattr(job, 'listing_id', None)
                    and (getattr(job, 'job_metadata', None) or {}).get('price_discovery')
                    and status in (JobStatus.COMPLETED.value, JobStatus.SCHEDULED.value)):
                discovery_live += 1
    except Exception:
        logger.warning("today: job scan failed", exc_info=True)

    autopilot = None
    try:
        from backend.app.core.database import ListingActionModel
        session = qm.SessionFactory()
        try:
            last = (session.query(ListingActionModel)
                    .order_by(ListingActionModel.executed_at.desc())
                    .first())
            if last is not None:
                # One cycle stamps every row with the same `now`.
                rows = (session.query(ListingActionModel)
                        .filter(ListingActionModel.executed_at == last.executed_at)
                        .all())
                autopilot = {
                    'last_run_at': last.executed_at,
                    'dry_run': bool(last.dry_run),
                    'offers': sum(1 for r in rows if r.action_type == 'offer'),
                    'markdowns': sum(1 for r in rows if r.action_type == 'markdown'),
                    'relists': sum(1 for r in rows if r.action_type == 'relist'),
                }
        finally:
            session.close()
    except Exception:
        logger.warning("today: autopilot summary failed", exc_info=True)

    return jsonify({
        'reviews': reviews,
        'queued': queued,
        'discovery_live': discovery_live,
        'autopilot': autopilot,
    })
