from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
import threading
from backend.app.blueprints.api.helpers import error_response
from backend.app.core.validator import validate_safe_path, ValidationError
from backend.app.core.logger import get_logger

queue_bp = Blueprint('queue', __name__)
logger = get_logger('api.queue')
_capture_lock = threading.Lock()


def _clean_capture_note(raw) -> str:
    """Normalize a seller-supplied capture note: str, trimmed, length-capped at 500."""
    if not isinstance(raw, str):
        return ""
    return raw.strip()[:500]

@queue_bp.route('/status')
def get_status():
    qm = current_app.queue_manager
    status = 'idle'
    if qm.is_processing(): status = 'processing'
    if qm.is_paused(): status = 'paused'
    
    stats = qm.get_stats()
    total = stats.get('total', 0)
    done = stats.get('completed', 0) + stats.get('failed', 0)
    percent = int((done / total * 100)) if total > 0 else 0
    
    current_job_data = None
    if hasattr(qm, 'current_job') and qm.current_job:
         j = qm.current_job
         current_job_data = {
             'id': j.id,
             'name': j.folder_name,
             'status': j.status.value if hasattr(j.status, 'value') else j.status
         }

    return jsonify({
        'status': status,
        'progress': {
            'current': done,
            'total': total,
            'percent': percent
        },
        'stats': stats,
        'current_job': current_job_data
    })

@queue_bp.route('/start', methods=['POST'])
def start_queue():
    qm = current_app.queue_manager
    qm.start_processing()
    return jsonify({'success': True})

@queue_bp.route('/pause', methods=['POST'])
def pause_queue():
    qm = current_app.queue_manager
    qm.pause()
    return jsonify({'success': True})

@queue_bp.route('/resume', methods=['POST'])
def resume_queue():
    qm = current_app.queue_manager
    qm.resume()
    return jsonify({'success': True})
    
@queue_bp.route('/retry', methods=['POST'])
def retry_failed():
    qm = current_app.queue_manager
    count = qm.retry_failed()
    return jsonify({'success': True, 'retried': count})

@queue_bp.route('/clear', methods=['POST'])
def clear_completed():
    qm = current_app.queue_manager
    data = request.get_json(silent=True) or {}
    delete_folders = data.get('deleteFolders', False)
    result = qm.clear_completed(delete_folders=delete_folders)
    return jsonify({'success': True, **result})

@queue_bp.route('/clear-failed', methods=['POST'])
def clear_failed():
    qm = current_app.queue_manager
    data = request.get_json(silent=True) or {}
    delete_folders = data.get('deleteFolders', False)
    result = qm.clear_failed(delete_folders=delete_folders)
    return jsonify({'success': True, **result})

@queue_bp.route('/purge-stale', methods=['POST'])
def purge_stale_jobs():
    """Remove jobs whose source folder no longer exists on disk."""
    qm = current_app.queue_manager
    result = qm.purge_missing_folders()
    return jsonify({'success': True, **result})

@queue_bp.route('/scan', methods=['POST'])
def scan_inbox_endpoint():
    """Trigger scan of inbox directory"""
    try:
        from backend.app.services.scanner_service import ScannerService
        inbox_dir = current_app.config['INBOX_DIR']
        scanner = ScannerService(inbox_dir)
        qm = current_app.queue_manager
        batch_id = f"inbox_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = scanner.scan_inbox(qm, batch_id=batch_id)
        return jsonify({
            'success': True,
            'count': result.get('added', 0),
            'batch_id': batch_id,
            'message': f"Scanned inbox. Added {result.get('added', 0)} jobs to queue (Batch: {batch_id})"
        })
    except Exception as e:
        return error_response(str(e))

@queue_bp.route('/batch-summary/<batch_id>')
def get_batch_summary(batch_id):
    """Retrieve summary statistics for a specific batch processing run."""
    qm = current_app.queue_manager
    summary = qm.get_batch_summary(batch_id)
    return jsonify(summary)

@queue_bp.route('/add-folder', methods=['POST'])
def add_folder_to_queue():
    """Add a local folder path to the queue (Bulk/Drag-Drop)"""
    data = request.json
    folder_path = data.get('path')
    if not folder_path:
        return error_response('Path required', 400)
    try:
        path_obj = validate_safe_path(folder_path)
    except ValidationError as e:
        return error_response(e.args[0], 403)
    if not path_obj.exists():
        return error_response('Folder not found on server', 404)
        
    from backend.app.core.constants import SUPPORTED_IMAGE_EXTENSIONS
    qm = current_app.queue_manager
    added_jobs = []
    batch_id = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    has_images = any(f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS for f in path_obj.iterdir() if f.is_file())
    
    if has_images:
        job = qm.add_folder(str(path_obj), batch_id=batch_id)
        added_jobs.append(job.id)
    else:
        subfolders = [f for f in path_obj.iterdir() if f.is_dir()]
        for sub in subfolders:
            if any(f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS for f in sub.iterdir() if f.is_file()):
                job = qm.add_folder(str(sub), batch_id=batch_id)
                added_jobs.append(job.id)
    if not added_jobs:
        return error_response('No valid item folders found', 400)
    return jsonify({
        'success': True,
        'count': len(added_jobs),
        'jobIds': added_jobs,
        'batch_id': batch_id,
        'message': f"Added {len(added_jobs)} jobs to queue (Batch: {batch_id})"
    })

@queue_bp.route('/capture', methods=['POST'])
def capture_item():
    """Register a pre-written captures/<id> folder as a job, auto-assign an eBay slot.

    The Hermes WhatsApp bridge writes an item's images directly into a folder
    under CAPTURES_DIR, then calls this endpoint with that folder's path.
    There is no file move and no use of the inbox watcher — the job is
    registered directly from the captures folder.

    Body: {"path": "<abs path under CAPTURES_DIR, already holding the item's images>"}

    GUARDRAIL: before registering, computes a perceptual photo-hash (dHash) of
    the staged images and compares against recent jobs' stored hashes
    (job_metadata['photo_hashes'], within DUP_LOOKBACK_DAYS). A near-match
    flags the new job pending_review ("possible duplicate of listing X") and
    skips starting processing — saving a wasted AI call on a re-send. A
    non-matching capture stores its own hashes for future comparisons and
    proceeds exactly as before. Different photos never trip this (conservative
    by design) so intentional variants/multiples are safe.
    """
    from backend.app.core.constants import (
        SUPPORTED_IMAGE_EXTENSIONS,
        get_next_optimal_listing_time,
        DUP_HASH_DISTANCE,
        DUP_LOOKBACK_DAYS,
    )
    from backend.app.services.listing_guardrails import compute_photo_hashes, find_duplicate
    from backend.app.services.queue_job import JobStatus
    from backend.app.services.whatsapp_notify import (
        get_whatsapp_origin, notify_whatsapp, build_duplicate_message,
    )

    data = request.json or {}
    raw_path = data.get('path')
    if not raw_path:
        return error_response('path required', 400)
    note = _clean_capture_note(data.get('note'))

    # Origin: when the Hermes WhatsApp bridge passes a chat_id, remember it so the
    # backend can message the user back later ("auto-decide + tell me").
    chat_id = (data.get('chat_id') or '').strip() or None
    origin = None
    if chat_id:
        origin = {'channel': 'whatsapp', 'chat_id': chat_id}
        try:
            origin['bridge_port'] = int(data.get('bridge_port')) if data.get('bridge_port') else None
        except (TypeError, ValueError):
            origin['bridge_port'] = None

    captures_root = current_app.config['CAPTURES_DIR']
    try:
        src = validate_safe_path(raw_path, base_dir=captures_root)
    except ValidationError as e:
        return error_response(e.args[0], 403)

    if not src.exists() or not src.is_dir():
        return error_response('path not found', 404)
    image_files = [f for f in src.iterdir()
                    if f.is_file() and f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS]
    if not image_files:
        return error_response('No images found in folder', 400)

    # GUARD: photo-hash dedup. Best-effort -- if hashing fails for any reason,
    # treat as non-duplicate rather than blocking the capture.
    photo_hashes = []
    duplicate = None
    try:
        photo_hashes = compute_photo_hashes([str(f) for f in image_files])
        cutoff = datetime.now() - timedelta(days=DUP_LOOKBACK_DAYS)
        qm = current_app.queue_manager
        recent_jobs = []
        for job in qm.get_all_jobs():
            hashes = (job.job_metadata or {}).get('photo_hashes')
            if not hashes:
                continue
            try:
                created = datetime.fromisoformat(job.created_at)
            except (TypeError, ValueError):
                continue
            if created < cutoff:
                continue
            recent_jobs.append({'id': job.id, 'listing_id': job.listing_id, 'photo_hashes': hashes})
        duplicate = find_duplicate(photo_hashes, recent_jobs, max_distance=DUP_HASH_DISTANCE)
    except Exception as e:
        logger.error(f"Photo-hash dedup check failed (proceeding as non-duplicate): {e}")
        duplicate = None

    qm = current_app.queue_manager
    with _capture_lock:
        # Compute the slot FIRST, then create the job already holding it, so the
        # job is persisted with its scheduled_time in a single transaction. If we
        # created the job slotless and assigned the slot in a second write, the
        # background worker could grab the pending job in between and fall back to
        # its own un-staggered scheduling — defeating the exclude_times staggering.
        batch_id = f"hermes_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        booked = qm.get_booked_schedule_times()
        slot = get_next_optimal_listing_time(exclude_times=booked)
        metadata = {'capture_source': 'hermes'}
        if note:
            metadata['note'] = note
        if photo_hashes:
            metadata['photo_hashes'] = photo_hashes
        if origin:
            metadata['origin'] = origin
        job = qm.add_folder(
            str(src),
            metadata=metadata,
            batch_id=batch_id,
            scheduled_time=slot,
        )

    if duplicate:
        dup_label = duplicate.get('listing_id') or duplicate.get('id')
        wa_origin = get_whatsapp_origin(metadata)
        if wa_origin:
            # Auto-decide + tell me: skip the duplicate, message the chat. The
            # item never lands in a review queue the WhatsApp user won't open.
            note_msg = build_duplicate_message(None, dup_label)
            qm.update_job(job.id, {
                'status': JobStatus.SKIPPED,
                'error_message': note_msg,
            })
            notify_whatsapp(wa_origin, note_msg)
            logger.info(f"Captured job {job.id} auto-skipped as duplicate (whatsapp): {dup_label}")
            return jsonify({
                'success': True,
                'job_id': job.id,
                'scheduled_time': slot,
                'scheduled': False,
                'duplicate': True,
                'auto_resolved': 'skipped',
                'decision_note': note_msg,
            })
        reason = f"possible duplicate of listing {dup_label}"
        qm.update_job(job.id, {
            'status': JobStatus.PENDING_REVIEW,
            'error_message': reason,
        })
        logger.info(f"Captured job {job.id} flagged pending_review: {reason}")
        return jsonify({
            'success': True,
            'job_id': job.id,
            'scheduled_time': slot,
            'scheduled': True,
            'duplicate': True,
            'review_reason': reason,
        })

    if not qm.is_processing() and not qm.is_paused():
        qm.start_processing()

    logger.info(f"Captured job {job.id} scheduled for {slot}")
    return jsonify({
        'success': True,
        'job_id': job.id,
        'scheduled_time': slot,
        'scheduled': True,
    })
