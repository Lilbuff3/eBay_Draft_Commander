from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
from backend.app.blueprints.api.helpers import error_response
from backend.app.core.validator import validate_safe_path, ValidationError
from backend.app.core.logger import get_logger

queue_bp = Blueprint('queue', __name__)
logger = get_logger('api.queue')

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
            'count': result.get('added_count', 0),
            'batch_id': batch_id,
            'message': f"Scanned inbox. Added {result.get('added_count', 0)} jobs to queue (Batch: {batch_id})"
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
