from flask import Blueprint, jsonify, request, current_app, send_file
from pathlib import Path
import os
import time
import uuid
from werkzeug.utils import secure_filename
from backend.app.blueprints.api.helpers import error_response
from backend.app.services.image_service import ImageService
from backend.app.core.constants import SUPPORTED_IMAGE_EXTENSIONS
from backend.app.core.validator import validate_price, validate_title, validate_isbn, ValidationError
from backend.app.core.logger import get_logger
from backend.app.services.queue_job import resolve_thumbnail

jobs_bp = Blueprint('jobs', __name__)
logger = get_logger('api.jobs')
image_service = ImageService()


def _ensure_inbox_dir() -> Path:
    """Get a writable inbox directory, falling back to data/inbox if INBOX_DIR is not writable.

    OneDrive-synced Desktop folders on Windows can appear to exist but be
    cloud-only placeholders — all mkdir/write operations fail with
    FileExistsError or FileNotFoundError. This helper detects that and
    falls back to a local directory.
    """
    inbox_dir = current_app.config['INBOX_DIR']
    try:
        inbox_dir.mkdir(parents=True, exist_ok=True)
        # Verify we can actually write a subfolder (OneDrive placeholders pass mkdir but fail here)
        probe = inbox_dir / '.write_test'
        probe.mkdir(exist_ok=True)
        probe.rmdir()
        return inbox_dir
    except (FileExistsError, FileNotFoundError, OSError) as e:
        # OneDrive cloud-only placeholder — fall back to local data/inbox
        fallback = current_app.config.get('DATA_DIR', Path.cwd() / 'data') / 'inbox'
        logger.warning(f"INBOX_DIR '{inbox_dir}' is not writable ({e}), falling back to '{fallback}'")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _resolve_display_name(j) -> str:
    """Extract the best available display name from AI data, falling back to folder name."""
    ai_data = j.ai_data if hasattr(j, 'ai_data') and j.ai_data else {}
    listing = ai_data.get('listing', {})
    return (
        getattr(j, 'user_title', None)
        or listing.get('suggested_title')
        or ai_data.get('seo_title')
        or j.folder_name
    )


def _resolve_thumb_url(j, qm) -> str | None:
    """Get thumbnail URL, with on-demand resolution and caching for cache misses."""
    thumb = getattr(j, 'thumbnail_name', None)
    if not thumb:
        thumb = resolve_thumbnail(j.folder_path)
        if thumb:
            try:
                qm.update_thumbnail(j.id, thumb)
            except Exception:
                pass
    return f'/api/job/{j.id}/image/{thumb}' if thumb else None


@jobs_bp.route('/jobs')
def get_jobs():
    qm = current_app.queue_manager
    jobs_data = []
    all_jobs = qm.get_all_jobs()
    for j in all_jobs:
        jobs_data.append({
            'id': j.id,
            'name': j.folder_name,
            'display_name': _resolve_display_name(j),
            'status': j.status.value if hasattr(j.status, 'value') else j.status,
            'folder_path': str(j.folder_path),
            'listing_id': getattr(j, 'listing_id', None),
            'offer_id': getattr(j, 'offer_id', None),
            'price': getattr(j, 'price', None),
            'error_type': getattr(j, 'error_type', None),
            'error_message': getattr(j, 'error_message', None),
            'started_at': getattr(j, 'started_at', None),
            'completed_at': getattr(j, 'completed_at', None),
            'thumbnail_url': _resolve_thumb_url(j, qm),
            'condition': j.job_metadata.get('condition') if hasattr(j, 'job_metadata') else None,
            'scheduled_time': getattr(j, 'scheduled_time', None)
        })
    return jsonify(jobs_data)

@jobs_bp.route('/job/<job_id>/details')
def get_job_details(job_id):
    qm = current_app.queue_manager
    job = qm.get_job_by_id(job_id)
    if not job:
        return error_response('Job not found', 404)
    job_folder = Path(job.folder_path)
    if not job_folder.exists():
        return error_response('Job folder not found', 404)
    
    ai_data = job.ai_data or {}
    images = []
    for file in job_folder.iterdir():
        if file.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            images.append({
                'name': file.name,
                'path': str(file),
                'url': f'/api/job/{job_id}/image/{file.name}'
            })
    
    listing = ai_data.get('listing', {})
    identification = ai_data.get('identification', {})
    condition_data = ai_data.get('condition', {})
    
    ai_title = (ai_data.get('seo_title') or listing.get('suggested_title') or 
                ai_data.get('title') or ai_data.get('ai_title') or job.folder_name)
    
    response = {
        'success': True,
        'id': job_id,
        'name': job.folder_name,
        'status': job.status.value if hasattr(job.status, 'value') else job.status,
        'folder_path': str(job.folder_path),
        'ai_title': ai_title,
        'ai_description': listing.get('description') or ai_data.get('description') or ai_data.get('ai_description') or '',
        'user_title': job.user_title,
        'user_price': job.user_price,
        'user_description': job.user_description,
        'scheduled_time': job.scheduled_time,
        'category_id': ai_data.get('category_id'),
        'category_name': ai_data.get('ebay_category_suggestion') or ai_data.get('category_name'),
        'category_keywords': ai_data.get('category_keywords', []),
        'item_specifics': job.item_specifics or ai_data.get('item_specifics') or ai_data.get('aspects') or {},
        'identification': identification,
        'suggested_price': listing.get('suggested_price') or ai_data.get('suggested_price') or ai_data.get('price'),
        'price_reasoning': listing.get('price_reasoning'),
        'pricing_data': {
            'confidence': identification.get('confidence_score'),
            'comparables': ai_data.get('comparables', [])[:5],
            'price_source': ai_data.get('price_source', 'AI estimate'),
            'market_price': ai_data.get('research', {}).get('market_price', {})
        },
        'condition': job.user_condition or condition_data if condition_data else ai_data.get('condition'),
        'condition_id': ai_data.get('condition_id'),
        'condition_description': ai_data.get('condition_description'),
        'analysis_mode': ai_data.get('analysis_mode'),
        'ebay_aspect_schema': ai_data.get('ebay_aspect_schema', []),
        'images': images,
        'image_count': len(images),
        'raw_metadata': job.job_metadata
    }
    return jsonify(response)

@jobs_bp.route('/job/<job_id>/update', methods=['POST'])
def update_job_metadata(job_id):
    qm = current_app.queue_manager
    data = request.json

    # Verify job exists
    job = qm.get_job_by_id(job_id)
    if not job:
        return error_response('Job not found', 404)

    # Build validated updates dict
    updates = {}
    try:
        if 'title' in data:
            updates['user_title'] = validate_title(data['title'])
        if 'price' in data:
            updates['user_price'] = str(validate_price(data['price']))
        if 'description' in data:
            updates['user_description'] = data['description']
        if 'condition' in data:
            updates['user_condition'] = data['condition']
        if 'item_specifics' in data:
            updates['item_specifics'] = data['item_specifics']
        if 'category_id' in data and data['category_id']:
            category_id = data['category_id']
            category_name = data.get('category_name', '')
            # Update ai_data with the corrected category
            ai_data = job.ai_data or {}
            ai_data['category_id'] = category_id
            ai_data['category_name'] = category_name
            ai_data['ebay_category_suggestion'] = category_name
            updates['ai_data'] = ai_data
            # Record correction for future items
            title = data.get('title') or job.user_title or job.folder_name
            from backend.app.services.category_correction_cache import get_correction_cache
            get_correction_cache().record(title, category_id, category_name)
        if 'fulfillmentPolicy' in data:
            metadata = updates.get('job_metadata', job.job_metadata or {})
            metadata['fulfillment_policy'] = data['fulfillmentPolicy']
            updates['job_metadata'] = metadata
        if 'ordered_images' in data:
            metadata = updates.get('job_metadata', job.job_metadata or {})
            metadata['ordered_images'] = data['ordered_images']
            updates['job_metadata'] = metadata
        if 'scheduled_time' in data:
            s_time_str = data['scheduled_time']
            if s_time_str:
                from datetime import datetime, timedelta, timezone
                try:
                    s_time = datetime.fromisoformat(s_time_str.replace('Z', '+00:00'))
                    # Ensure timezone-aware for comparison
                    if s_time.tzinfo is None:
                        s_time = s_time.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    if s_time < now:
                        raise ValidationError("Scheduled time cannot be in the past.")
                    if s_time > now + timedelta(days=21):
                        raise ValidationError("Scheduled time cannot be more than 21 days in the future.")
                    updates['scheduled_time'] = s_time_str
                except ValueError:
                    raise ValidationError("Invalid scheduled_time format. Must be ISO 8601.")
            else:
                updates['scheduled_time'] = None
    except ValidationError as e:
        return error_response(e.args[0], 400)

    # Persist directly to database
    if updates:
        qm.update_job(job_id, updates)

    if data.get('process_now'):
        from backend.app.services.queue_manager import JobStatus
        
        # Mark as user approved so it doesn't get kicked back to review queue
        metadata = job.job_metadata or {}
        metadata['user_approved'] = True
        qm.update_job(job_id, {'job_metadata': metadata})
        
        if job.status in [JobStatus.FAILED, JobStatus.PENDING, JobStatus.COMPLETED, JobStatus.NEEDS_REVIEW, JobStatus.PENDING_REVIEW]:
            qm.retry_job(job_id)
        if not qm.is_processing():
            qm.start_processing()

    return jsonify({'success': True, 'message': 'Job updated'})

@jobs_bp.route('/jobs/bulk-update', methods=['POST'])
def bulk_update_jobs():
    qm = current_app.queue_manager
    data = request.json
    job_ids = data.get('jobIds', [])
    updates = data.get('updates', {})
    if not job_ids:
        return error_response('No jobIds provided', 400)

    updated_count = 0
    errors = []
    for job_id in job_ids:
        try:
            # Build per-job update dict
            job_updates = {}
            if 'condition' in updates:
                job_updates['user_condition'] = updates['condition']
            if 'price' in updates:
                job_updates['user_price'] = str(validate_price(updates['price']))
            if updates.get('reset_status'):
                from backend.app.services.queue_manager import JobStatus
                job_updates['status'] = JobStatus.PENDING
                job_updates['error_type'] = None
                job_updates['error_message'] = None

            if job_updates:
                if qm.update_job(job_id, job_updates):
                    updated_count += 1
                else:
                    errors.append(f"Job {job_id} not found")
        except Exception as e:
            errors.append(f"Failed to update {job_id}: {e}")

    return jsonify({'success': True, 'count': updated_count, 'errors': errors})

@jobs_bp.route('/jobs/bulk-delete', methods=['POST'])
def bulk_delete_jobs():
    qm = current_app.queue_manager
    data = request.json
    job_ids = data.get('jobIds', [])
    delete_folders = data.get('deleteFolders', False)
    if not job_ids: return error_response('No jobIds provided', 400)
    deleted_count = 0
    errors = []
    for job_id in job_ids:
        if qm.remove_job(job_id, delete_folder=delete_folders): deleted_count += 1
        else: errors.append(f"Failed to delete {job_id}")
    return jsonify({'success': True, 'count': deleted_count, 'errors': errors})

@jobs_bp.route('/job/<job_id>/images')
def get_job_images(job_id):
    qm = current_app.queue_manager
    images = image_service.get_job_images(job_id, qm)
    if images is None: return error_response('Job not found', 404)
    return jsonify({'images': images, 'count': len(images)})

@jobs_bp.route('/job/<job_id>/image/<filename>')
def serve_job_image(job_id, filename):
    qm = current_app.queue_manager
    path = image_service.get_image_path(job_id, filename, qm)
    if not path: return error_response('Image not found', 404)
    return send_file(path)

@jobs_bp.route('/create-from-metadata', methods=['POST'])
def create_job_from_metadata():
    try:
        data = request.json
        if not data: return error_response('No metadata provided', 400)
        qm = current_app.queue_manager
        folder_name = f"metadata_import_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        inbox_dir = _ensure_inbox_dir()
        job_folder = inbox_dir / folder_name
        job_folder.mkdir(exist_ok=True)
        image_url = data.get('thumbnail')
        if image_url:
            try:
                import requests
                img_resp = requests.get(image_url, timeout=10)
                if img_resp.status_code == 200:
                    ext = 'png' if 'png' in image_url else 'jpg'
                    with open(job_folder / f"cover.{ext}", 'wb') as f: f.write(img_resp.content)
            except Exception as e: logger.warning(f"Failed to download thumbnail: {e}")
        metadata = {
            'user_title': data.get('title'), 'user_isbn': data.get('isbn'), 'user_description': data.get('description'),
            'source_data': data, 'created_at': time.time(), 'notes': f"Imported from {data.get('source', 'metadata')}"
        }
        job = qm.add_folder(str(job_folder), metadata=metadata)
        return jsonify({'success': True, 'jobId': job.id, 'message': 'Job created from metadata'})
    except Exception as e: return error_response(str(e))

@jobs_bp.route('/upload', methods=['POST'])
def upload_files():
    if 'files[]' not in request.files: return error_response('No files provided', 400)
    files = request.files.getlist('files[]')
    if not files: return error_response('No files selected', 400)
    qm = current_app.queue_manager
    folder_name = f"mobile_upload_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    inbox_dir = _ensure_inbox_dir()
    job_folder = inbox_dir / folder_name
    job_folder.mkdir(exist_ok=True)
    saved_count = 0
    try:
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(str(job_folder / filename)); saved_count += 1
        if saved_count == 0: return error_response('No valid files saved', 400)
        job = qm.add_folder(str(job_folder))
        return jsonify({'success': True, 'message': f'Successfully uploaded {saved_count} photos', 'jobId': job.id, 'folder': folder_name})
    except Exception as e: return error_response(str(e))

@jobs_bp.route('/listing/create-from-photos', methods=['POST'])
def create_listing_from_photos():
    try:
        files = []
        for key in request.files: files.append(request.files[key])
        if not files: return error_response('No photos provided', 400)
        qm = current_app.queue_manager
        folder_name = f"web_upload_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        inbox_dir = _ensure_inbox_dir()
        job_folder = inbox_dir / folder_name
        job_folder.mkdir(exist_ok=True)
        saved_count = 0
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(str(job_folder / filename)); saved_count += 1
        try:
            metadata = {
                'user_title': validate_title(request.form.get('itemName')) if request.form.get('itemName') else None,
                'user_price': str(validate_price(request.form.get('price'))) if request.form.get('price') else None,
                'user_description': request.form.get('description'),
                'created_at': time.time()
            }
        except ValidationError as e: return error_response(e.args[0], 400)
        job = qm.add_folder(str(job_folder), metadata=metadata)
        if not qm.is_processing(): qm.start_processing()
        return jsonify({'success': True, 'jobId': job.id, 'message': 'Listing created and queued for processing'})
    except Exception as e: return error_response(str(e))

@jobs_bp.route('/tools/photo/save', methods=['POST'])
def save_photo_edits():
    qm = current_app.queue_manager
    data = request.json
    job_id = data.get('jobId')
    edits = data.get('edits', {})
    result, status = image_service.save_edits(job_id, edits, qm)
    return jsonify(result), status
