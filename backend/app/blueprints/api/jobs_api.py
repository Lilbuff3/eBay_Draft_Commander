from flask import Blueprint, jsonify, request, current_app, send_file
from pathlib import Path
import os
import time
import uuid
from werkzeug.utils import secure_filename
from backend.app.blueprints.api.helpers import error_response
from backend.app.services.image_service import ImageService
from backend.app.services.ebay_service import eBayService
from backend.app.core.constants import SUPPORTED_IMAGE_EXTENSIONS, EBAY_FINAL_VALUE_FEE_RATE, EBAY_PAYMENT_PROCESSING_FEE
from backend.app.core.validator import validate_price, validate_title, validate_isbn, validate_condition, is_allowed_image_file, ValidationError
from backend.app.core.logger import get_logger
from backend.app.services.queue_job import resolve_thumbnail
from backend.app.services.pricing_engine import format_price_source

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


def _merge_specifics_into_schema(schema: list, specifics: dict) -> list:
    """Merge item_specifics values into aspect schema as currentValue for frontend display."""
    if not specifics:
        return schema
    enriched = []
    for aspect in schema:
        name = aspect.get('name')
        if name and name in specifics:
            aspect = {**aspect, 'currentValue': specifics[name]}
        enriched.append(aspect)
    return enriched


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

    ai_data = job.ai_data or {}
    images = []
    if job_folder.exists():
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
        'ai_description': listing.get('description') or listing.get('description_html') or ai_data.get('description') or ai_data.get('ai_description') or '',
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
            'price_source_label': format_price_source(
                ai_data.get('pricing_source', ''),
                comp_count=len(ai_data.get('pricing_comps', []))
            ),
            'market_price': ai_data.get('research', {}).get('market_price', {})
        },
        'condition': job.user_condition or (condition_data.get('state') if isinstance(condition_data, dict) else condition_data) or '',
        'condition_id': ai_data.get('condition_id'),
        'condition_description': ai_data.get('condition_description'),
        'analysis_mode': ai_data.get('analysis_mode'),
        'ebay_aspect_schema': _merge_specifics_into_schema(
            ai_data.get('ebay_aspect_schema', []),
            job.item_specifics or ai_data.get('item_specifics') or {}
        ),
        'image_urls': ai_data.get('image_urls', []),
        'images': images,
        'image_count': len(images),
        'confidence_score': job.confidence_score,
        'price': job.price,
        'timing': job.timing,
        'raw_metadata': job.job_metadata
    }

    # --- Profit Breakdown ---
    listing_price = float(job.price or ai_data.get('suggested_price') or ai_data.get('price') or 0)
    shipping_cost_val = float(ai_data.get('shipping_cost', 6.50))
    ebay_fee = round(listing_price * EBAY_FINAL_VALUE_FEE_RATE, 2) if listing_price > 0 else 0
    payment_fee = EBAY_PAYMENT_PROCESSING_FEE if listing_price > 0 else 0
    take_home = round(listing_price - ebay_fee - payment_fee - shipping_cost_val, 2) if listing_price > 0 else 0

    response['profit_breakdown'] = {
        'listing_price': listing_price,
        'ebay_fee': ebay_fee,
        'ebay_fee_rate': EBAY_FINAL_VALUE_FEE_RATE,
        'payment_fee': payment_fee,
        'shipping_cost': shipping_cost_val,
        'shipping_method': ai_data.get('shipping_method', 'standard'),
        'take_home': take_home,
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
            updates['user_condition'] = validate_condition(data['condition'])
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
            metadata['force_image_reupload'] = True  # Reorder invalidates cached EPS URLs
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
        metadata = dict(updates.get('job_metadata', job.job_metadata or {}))
        metadata['user_approved'] = True
        qm.update_job(job_id, {'job_metadata': metadata})
        
        if job.status in [JobStatus.FAILED, JobStatus.PENDING, JobStatus.COMPLETED, JobStatus.NEEDS_REVIEW, JobStatus.PENDING_REVIEW]:
            qm.retry_job(job_id)
        if not qm.is_processing():
            qm.start_processing()

    return jsonify({'success': True, 'message': 'Job updated'})

@jobs_bp.route('/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a captured/scheduled item: end its eBay listing (if any), remove the job."""
    qm = current_app.queue_manager
    job = qm.get_job_by_id(job_id)
    if not job:
        return error_response('Job not found', 404)

    listing_id = getattr(job, 'listing_id', None)
    if listing_id:
        try:
            ended = eBayService().end_listing(str(listing_id))
        except Exception as e:
            logger.exception("cancel_job: end_listing failed")
            return error_response(f'Failed to end eBay listing: {e}', 502)
        if not ended.get('success'):
            return error_response(f"eBay end failed: {ended.get('error')}", 502)

    qm.remove_job(job_id, delete_folder=True)
    return jsonify({'success': True, 'job_id': job_id, 'ebay_ended': bool(listing_id)})

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

def _validate_thumbnail_url(url: str) -> bool:
    """Validate thumbnail URL: must be https/http, not internal IP."""
    from urllib.parse import urlparse
    import ipaddress
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        hostname = parsed.hostname or ''
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            pass  # hostname is a domain name, not an IP
        if hostname in ('localhost', 'metadata.google.internal'):
            return False
        return True
    except Exception:
        return False


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
        if image_url and _validate_thumbnail_url(image_url):
            try:
                import requests as http_requests
                img_resp = http_requests.get(image_url, timeout=10, allow_redirects=False)
                if img_resp.status_code == 200 and len(img_resp.content) < 10 * 1024 * 1024:
                    ext = 'png' if 'png' in image_url else 'jpg'
                    with open(job_folder / f"cover.{ext}", 'wb') as f:
                        f.write(img_resp.content)
            except Exception as e:
                logger.warning(f"Failed to download thumbnail: {e}")
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
    rejected = []
    try:
        for file in files:
            if file and file.filename:
                if not is_allowed_image_file(file.filename):
                    rejected.append(file.filename)
                    continue
                filename = secure_filename(file.filename)
                file.save(str(job_folder / filename)); saved_count += 1
        if saved_count == 0:
            job_folder.rmdir()
            return error_response(f"No supported image files. Rejected: {', '.join(rejected)}" if rejected else 'No valid files saved', 400)
        
        metadata = {}
        try:
            if request.form.get('title'):
                metadata['user_title'] = validate_title(request.form.get('title'))
            if request.form.get('condition'):
                metadata['user_condition'] = validate_condition(request.form.get('condition'))
            if request.form.get('category'):
                # Soft hint from category-first capture (clothing/shoes/electronics/books)
                metadata['category_hint'] = request.form.get('category')[:32]
        except ValidationError as e:
            return error_response(str(e), 400)
            
        job = qm.add_folder(str(job_folder), metadata=metadata if metadata else None)
        if not qm.is_processing(): qm.start_processing()
        msg = f'Successfully uploaded {saved_count} photos'
        if rejected:
            msg += f" ({len(rejected)} skipped, unsupported type: {', '.join(rejected)})"
        return jsonify({'success': True, 'message': msg, 'jobId': job.id, 'folder': folder_name, 'rejected': rejected})
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
            if file and file.filename and is_allowed_image_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(str(job_folder / filename)); saved_count += 1
        if saved_count == 0:
            job_folder.rmdir()
            return error_response('No supported image files provided', 400)
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

@jobs_bp.route('/tools/photo/enhance', methods=['POST'])
def auto_enhance_photo():
    """Apply auto-enhancement to a job's image using PIL"""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return error_response('Server missing Pillow library', 500)

    data = request.json
    job_id = data.get('jobId')
    image_name = data.get('imageName')

    if not job_id:
        return error_response('jobId is required', 400)

    qm = current_app.queue_manager
    job = qm.get_job_by_id(job_id)
    if not job:
        return error_response('Job not found', 404)

    folder_path = Path(job.folder_path)
    if not folder_path.exists():
        return error_response('Job folder not found', 404)

    # Find the target image
    if image_name:
        target = folder_path / image_name
        if not target.exists():
            return error_response(f'Image {image_name} not found', 404)
    else:
        # Use the first image in the folder
        image_files = sorted(
            f for f in folder_path.iterdir()
            if f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )
        if not image_files:
            return error_response('No images found in job folder', 404)
        target = image_files[0]

    try:
        with Image.open(target) as img:
            img_rgb = img.convert('RGB')
            stat = ImageStat.Stat(img_rgb)

            # Mean brightness across channels (0-255)
            mean_brightness = sum(stat.mean) / 3.0
            # Ideal midpoint is 128
            # Map to 0-100 slider scale where 50 = no change
            # If mean < 128, image is dark -> suggest brightness > 50
            # If mean > 128, image is bright -> suggest brightness < 50
            brightness_offset = (128 - mean_brightness) / 128.0 * 15  # max +/-15 from center
            brightness = int(max(35, min(65, 50 + brightness_offset)))

            # Contrast: slight boost for low-contrast images
            # Use stddev as a proxy for contrast
            mean_stddev = sum(stat.stddev) / 3.0
            # Low stddev = flat/low-contrast image -> boost more
            if mean_stddev < 40:
                contrast = 60  # noticeable boost
            elif mean_stddev < 60:
                contrast = 55  # slight boost
            else:
                contrast = 50  # already good contrast

            # Saturation: mild boost unless already very saturated
            saturation = 55 if mean_stddev < 80 else 50

            # Sharpness: always a slight boost for product photos
            sharpness = 58

        return jsonify({
            'success': True,
            'adjustments': {
                'brightness': brightness,
                'contrast': contrast,
                'saturation': saturation,
                'sharpness': sharpness
            }
        })
    except Exception as e:
        logger.exception(f"Auto-enhance analysis failed for job {job_id}")
        return error_response(f'Enhancement analysis failed: {e}', 500)


@jobs_bp.route('/tools/photo/save', methods=['POST'])
def save_photo_edits():
    qm = current_app.queue_manager
    data = request.json
    job_id = data.get('jobId')
    edits = data.get('edits', {})
    result, status = image_service.save_edits(job_id, edits, qm)
    return jsonify(result), status


@jobs_bp.route('/job/<job_id>/preview', methods=['GET', 'POST'])
def get_job_preview(job_id):
    qm = current_app.queue_manager
    job = qm.get_job_by_id(job_id)
    if not job:
        return error_response('Job not found', 404)

    # 1. Return frozen HTML description if already completed/scheduled and saved in DB
    # Only if it's a GET request (POST request implies live editing/previewing)
    if request.method == 'GET' and job.description:
        return job.description

    # 2. Dynamic template render for drafts (or POST edits)
    try:
        from backend.app.services.processor_service import ProcessorService
        processor = ProcessorService()

        ai_data = job.ai_data or {}
        listing = ai_data.get('listing', {})
        
        post_data = {}
        if request.method == 'POST':
            try:
                post_data = request.json or {}
            except Exception:
                pass
        
        # Priority: POST override -> user override -> resolved job title -> AI suggested title -> folder name
        title = post_data.get('title') or job.user_title or job.title or listing.get('suggested_title') or ai_data.get('seo_title') or job.folder_name
        
        # Priority: POST override -> user override -> AI HTML description -> AI plain text description -> fallback
        raw_description = post_data.get('description') or job.user_description or listing.get('description_html') or listing.get('description') or ai_data.get('description') or ''
        
        # Priority: POST override -> user override -> resolved job condition -> default
        condition = post_data.get('condition') or job.user_condition or job.condition or 'USED_GOOD'
        
        # Resolve images as local serving URLs
        images = []
        job_folder = Path(job.folder_path)
        ordered_images = post_data.get('ordered_images') or (job.job_metadata.get('ordered_images') if job.job_metadata else None)
        
        if job_folder.exists():
            local_files = [f.name for f in job_folder.iterdir() if f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS and not f.name.endswith('.orig')]
            if ordered_images:
                img_map = {name: name for name in local_files}
                sorted_names = []
                for name in ordered_images:
                    if name in img_map:
                        sorted_names.append(img_map.pop(name))
                sorted_names.extend(sorted(img_map.values()))
                local_files = sorted_names
            else:
                local_files = sorted(local_files)
                
            for filename in local_files[:12]:
                images.append(f'/api/job/{job_id}/image/{filename}')

        # Clean aspect values
        aspects = post_data.get('item_specifics') or job.item_specifics or ai_data.get('item_specifics') or {}
        cleaned_aspects = {}
        for k, v in aspects.items():
            if not v:
                continue
            val = v[0] if isinstance(v, list) else v
            cleaned_aspects[k] = [str(val)]

        research = ai_data.get('research', {})

        rendered = processor._render_listing_template(
            title=title,
            description=raw_description,
            images=images,
            aspects=cleaned_aspects,
            condition=condition,
            research=research
        )
        return rendered.get("html", "")
    except Exception as e:
        logger.exception(f"Preview rendering failed for job {job_id}")
        return f"<h3>Preview failed: {e}</h3>"


