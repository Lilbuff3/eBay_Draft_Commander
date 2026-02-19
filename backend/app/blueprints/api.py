from flask import Blueprint, jsonify, request, current_app, send_file
from werkzeug.utils import secure_filename
import os
import uuid
import time
from pathlib import Path
from backend.app.services.ebay_service import eBayService
from backend.app.services.image_service import ImageService
from backend.app.services.ebay import policies as ebay_policies
from backend.app.core.settings_manager import get_settings_manager
from backend.app.core.logger import get_logger
from backend.app.core.validator import validate_price, validate_title, validate_isbn, validate_safe_path, ValidationError

api_bp = Blueprint('api', __name__)
logger = get_logger('api')
ebay_service = eBayService()
image_service = ImageService()

def error_response(message, code=500, details=None):
    """Standardized error response helper"""
    response = {'success': False, 'error': str(message)}
    if details:
        response['details'] = details
    return jsonify(response), code

# --- Upload Endpoint (Mobile Support) ---

@api_bp.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads from mobile/web and create a new job"""
    if 'files[]' not in request.files:
        return error_response('No files provided', 400)
        
    files = request.files.getlist('files[]')
    if not files:
        return error_response('No files selected', 400)
        
    qm = current_app.queue_manager
    
    # Create a unique folder for this upload
    # Using timestamp + short UUID for uniqueness
    folder_name = f"mobile_upload_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    
    # Determine inbox path (using qm.base_path parent or config default)
    # Assuming standard project structure: backend/../inbox
    # But safer to ask Config or use a known relative path
    # Use standard INBOX_DIR from config
    inbox_dir = current_app.config['INBOX_DIR']
    inbox_dir = current_app.config['INBOX_DIR']
    inbox_dir.mkdir(parents=True, exist_ok=True)

    job_folder = inbox_dir / folder_name
    job_folder.mkdir(exist_ok=True)
    
    saved_count = 0
    try:
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                save_path = job_folder / filename
                file.save(str(save_path))
                saved_count += 1
                
        if saved_count == 0:
            return jsonify({'success': False, 'error': 'No valid files saved'}), 400

        # Register with QueueManager
        # add_folder takes string path
        job = qm.add_folder(str(job_folder))
        
        return jsonify({
            'success': True, 
            'message': f'Successfully uploaded {saved_count} photos',
            'jobId': job.id,
            'folder': folder_name
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/listing/create-from-photos', methods=['POST'])
def create_listing_from_photos():
    """Handle upload + metadata from QuickListingForm"""
    try:
        # 1. Handle Files
        files = []
        # Frontend sends 'photo0', 'photo1', etc.
        for key in request.files:
            files.append(request.files[key])
            
        if not files:
            return jsonify({'success': False, 'error': 'No photos provided'}), 400
            
        qm = current_app.queue_manager
        folder_name = f"web_upload_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        
        # Resolve 'inbox' path (reusing logic from /upload)
        # Use standard INBOX_DIR from config
        inbox_dir = current_app.config['INBOX_DIR']
        inbox_dir.mkdir(parents=True, exist_ok=True)
            
        job_folder = inbox_dir / folder_name
        job_folder.mkdir(exist_ok=True)
        
        saved_count = 0
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(str(job_folder / filename))
                saved_count += 1
                
        # 2. Handle Metadata (passed directly to qm.add_folder)
        try:
            metadata = {
                'user_title': validate_title(request.form.get('itemName')) if request.form.get('itemName') else None,
                'user_price': str(validate_price(request.form.get('price'))) if request.form.get('price') else None,
                'user_description': request.form.get('description'),
                'created_at': time.time()
            }
        except ValidationError as e:
            return error_response(e.args[0], 400)
        
        # 3. Queue Job with metadata
        job = qm.add_folder(str(job_folder), metadata=metadata)
        
        # Auto-start processing if idle
        if not qm.is_processing():
            qm.start_processing()
            
        return jsonify({
            'success': True,
            'jobId': job.id,
            'message': 'Listing created and queued for processing'
        })
        
    except Exception as e:
        logger.error(f"Error in create-from-photos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# --- Scanner Endpoint ---

@api_bp.route('/scan', methods=['POST'])
def scan_inbox_endpoint():
    """Trigger scan of inbox directory"""
    try:
        from backend.app.services.scanner_service import ScannerService
        
        # Use config INBOX_DIR
        inbox_dir = current_app.config['INBOX_DIR']
            
        scanner = ScannerService(inbox_dir)
        qm = current_app.queue_manager
        
        result = scanner.scan_inbox(qm)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/jobs/create-from-metadata', methods=['POST'])
def create_job_from_metadata():
    """Create a new job from provided metadata (e.g. from Book Lookup)"""
    try:
        data = request.json
        if not data:
            return error_response('No metadata provided', 400)
            
        qm = current_app.queue_manager
        
        # 1. Create Folder
        folder_name = f"metadata_import_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        inbox_dir = current_app.config['INBOX_DIR']
        inbox_dir.mkdir(parents=True, exist_ok=True)
        job_folder = inbox_dir / folder_name
        job_folder.mkdir(exist_ok=True)
        
        # 2. Handle Thumbnail (if provided URL)
        image_url = data.get('thumbnail')
        if image_url:
            try:
                import requests
                img_resp = requests.get(image_url, timeout=10)
                if img_resp.status_code == 200:
                    # Guess extension or default to jpg
                    ext = 'jpg'
                    if 'png' in image_url: ext = 'png'
                    with open(job_folder / f"cover.{ext}", 'wb') as f:
                        f.write(img_resp.content)
            except Exception as e:
                logger.warning(f"Failed to download thumbnail: {e}")
                
        # 3. Prepare Metadata (passed directly)
        # Ensure we keep the original data plus mapped fields for AI
        metadata = {
            'user_title': data.get('title'),
            'user_isbn': data.get('isbn'),
            'user_description': data.get('description'),
            'source_data': data, # Keep full original data
            'created_at': time.time(),
            'notes': f"Imported from {data.get('source', 'metadata')}"
        }
        
        # 4. Queue Job
        job = qm.add_folder(str(job_folder), metadata=metadata)
        
        return jsonify({
            'success': True,
            'jobId': job.id,
            'message': 'Job created from metadata'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Lookup Endpoints ---

@api_bp.route('/lookup/book', methods=['POST'])
def lookup_book_post():
    """Lookup book details via ISBN (POST method)"""
    data = request.json
    isbn = data.get('isbn')
    
    if not isbn:
        return jsonify({'success': False, 'error': 'ISBN is required'}), 400
        
    try:
        isbn = validate_isbn(isbn)
        from backend.app.services.book_service import BookService
        svc = BookService()
        result = svc.lookup_isbn(isbn)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# --- eBay Connection Status ---

@api_bp.route('/ebay/status')
def get_ebay_status():
    """Check eBay API connection status"""
    result, status = ebay_service.check_connection_status()
    return jsonify(result), status

# --- Queue Control Endpoints ---

@api_bp.route('/status')
def get_status():
    qm = current_app.queue_manager
    
    status = 'idle'
    if qm.is_processing(): status = 'processing'
    if qm.is_paused(): status = 'paused'
    
    # Progress
    stats = qm.get_stats()
    total = stats.get('total', 0)
    # calculate done based on stats if get_stats returns counts
    done = stats.get('completed', 0) + stats.get('failed', 0)
    percent = int((done / total * 100)) if total > 0 else 0
    
    # Current job
    current_job_data = None
    # Access current_job safely if it exists on qm
    if hasattr(qm, 'current_job') and qm.current_job:
         # Assuming QueueJob has to_dict or we construct it
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

@api_bp.route('/jobs')
def get_jobs():
    qm = current_app.queue_manager
    jobs_data = []
    if hasattr(qm, 'jobs'):
        for j in qm.jobs:
            jobs_data.append({
                'id': j.id,
                'name': j.folder_name,
                'status': j.status.value if hasattr(j.status, 'value') else j.status,
                'folder_path': str(j.folder_path),
                'listing_id': getattr(j, 'listing_id', None),
                'price': getattr(j, 'price', None),
                'error_type': getattr(j, 'error_type', None),
                # Add thumbnail URL if available
                'thumbnail_url': f'/api/job/{j.id}/image/cover.jpg' if (Path(j.folder_path) / 'cover.jpg').exists() else (
                    f'/api/job/{j.id}/image/{next((f.name for f in Path(j.folder_path).iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}), "")}'
                    if Path(j.folder_path).exists() and any(f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} for f in Path(j.folder_path).iterdir())
                    else None
                ),
                'condition': j.job_metadata.get('condition') if hasattr(j, 'job_metadata') else None,
                'scheduled_time': getattr(j, 'scheduled_time', None)
            })
    return jsonify(jobs_data)

@api_bp.route('/job/<job_id>/details')
def get_job_details(job_id):
    """
    Get full job details including AI analysis results.
    Reads from both job.json (user overrides) and ai_data.json (AI analysis).
    Returns title, description, category, item specifics, pricing, and images.
    """
    import json
    import os
    
    qm = current_app.queue_manager
    job = qm.get_job_by_id(job_id)
    
    if not job:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
    
    job_folder = Path(job.folder_path)
    if not job_folder.exists():
        return jsonify({'success': False, 'error': 'Job folder not found'}), 404
    
    # Use data directly from Job Object (from DB)
    ai_data = job.ai_data or {}
    
    # Get images in folder
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    images = []
    if job_folder.exists():
        for file in job_folder.iterdir():
            if file.suffix.lower() in image_extensions:
                images.append({
                    'name': file.name,
                    'path': str(file),
                    'url': f'/api/job/{job_id}/image/{file.name}'
                })
    
    # Build response with AI analysis data
    # AI data has nested structure: identification, listing, condition, etc.
    identification = ai_data.get('identification', {})
    listing = ai_data.get('listing', {})
    condition_data = ai_data.get('condition', {})
    
    # Get SEO title if available (from Phase 3 mapping), else use listing title
    ai_title = (
        ai_data.get('seo_title') or 
        listing.get('suggested_title') or 
        ai_data.get('title') or 
        ai_data.get('ai_title') or 
        job.folder_name
    )
    
    # Determine effectively valid values (User override > AI > existing)
    
    response = {
        'success': True,
        'id': job_id,
        'name': job.folder_name,
        'status': job.status.value if hasattr(job.status, 'value') else job.status,
        'folder_path': str(job.folder_path),
        
        # AI-Generated Content
        'ai_title': ai_title,
        'ai_description': listing.get('description') or ai_data.get('description') or ai_data.get('ai_description') or '',
        
        # User Overrides (from DB)
        'user_title': job.user_title,
        'user_price': job.user_price,
        'user_description': job.user_description,
        
        # Category
        'category_id': ai_data.get('category_id'),
        'category_name': ai_data.get('ebay_category_suggestion') or ai_data.get('category_name'),
        'category_keywords': ai_data.get('category_keywords', []),
        
        # Item Specifics
        'item_specifics': job.item_specifics or ai_data.get('item_specifics') or ai_data.get('aspects') or {},
        
        # Identification (brand, model, mpn, etc.)
        'identification': identification,
        
        # Pricing
        'suggested_price': listing.get('suggested_price') or ai_data.get('suggested_price') or ai_data.get('price'),
        'price_reasoning': listing.get('price_reasoning'),
        'pricing_data': {
            'confidence': identification.get('confidence_score'),
            'comparables': ai_data.get('comparables', [])[:5],  # Limit to 5 comps
            'price_source': ai_data.get('price_source', 'AI estimate'),
            'market_price': ai_data.get('research', {}).get('market_price', {})
        },
        
        # Condition
        'condition': job.user_condition or condition_data if condition_data else ai_data.get('condition'),
        'condition_id': ai_data.get('condition_id'),
        'condition_description': ai_data.get('condition_description'),
        
        # Analysis Mode
        'analysis_mode': ai_data.get('analysis_mode'),
        
        # Images
        'images': images,
        'image_count': len(images),
        
        # Raw metadata for debugging
        'raw_metadata': job.job_metadata
    }
    
    return jsonify(response)

@api_bp.route('/start', methods=['POST'])
def start_queue():
    qm = current_app.queue_manager
    qm.start_processing()
    return jsonify({'success': True})

@api_bp.route('/pause', methods=['POST'])
def pause_queue():
    qm = current_app.queue_manager
    qm.pause()
    return jsonify({'success': True})

@api_bp.route('/resume', methods=['POST'])
def resume_queue():
    qm = current_app.queue_manager
    qm.resume()
    return jsonify({'success': True})
    
@api_bp.route('/retry', methods=['POST'])
def retry_failed():
    qm = current_app.queue_manager
    count = qm.retry_failed()
    return jsonify({'success': True, 'retried': count})

@api_bp.route('/clear', methods=['POST'])
def clear_completed():
    qm = current_app.queue_manager
    qm.clear_completed()
    return jsonify({'success': True})

@api_bp.route('/queue/add-folder', methods=['POST'])
def add_folder_to_queue():
    """Add a local folder path to the queue (Bulk/Drag-Drop)"""
    data = request.json
    folder_path = data.get('path')
    
    if not folder_path:
        return jsonify({'success': False, 'error': 'Path required'}), 400
        
    try:
        path_obj = validate_safe_path(folder_path)
    except ValidationError as e:
        return error_response(e.args[0], 403)

    if not path_obj.exists():
        return jsonify({'success': False, 'error': 'Folder not found on server'}), 404
        
    qm = current_app.queue_manager
    added_jobs = []
    
    # Check if this is a single item folder (contains images directly)
    # or a batch folder (contains subfolders)
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    has_images = any(f.suffix.lower() in image_extensions for f in path_obj.iterdir() if f.is_file())
    
    if has_images:
        # Single Job
        job = qm.add_folder(str(path_obj))
        added_jobs.append(job.id)
    else:
        # Batch Mode: Scan subfolders
        subfolders = [f for f in path_obj.iterdir() if f.is_dir()]
        for sub in subfolders:
            # Check if subfolder has images
            if any(f.suffix.lower() in image_extensions for f in sub.iterdir() if f.is_file()):
                job = qm.add_folder(str(sub))
                added_jobs.append(job.id)
                
    if not added_jobs:
        return jsonify({'success': False, 'error': 'No valid item folders found'}), 400
        
    return jsonify({
        'success': True,
        'count': len(added_jobs),
        'jobIds': added_jobs,
        'message': f"Added {len(added_jobs)} jobs to queue"
    })

# --- Policy Endpoints ---

@api_bp.route('/policies/fulfillment')
def get_fulfillment_policies():
    data = ebay_policies.get_fulfillment_policies()
    defaults = ebay_policies.get_current_defaults()
    return jsonify({'policies': data, 'default': defaults.get('fulfillment')})

@api_bp.route('/policies/payment')
def get_payment_policies():
    data = ebay_policies.get_payment_policies()
    defaults = ebay_policies.get_current_defaults()
    return jsonify({'policies': data, 'default': defaults.get('payment')})

@api_bp.route('/policies/return')
def get_return_policies():
    data = ebay_policies.get_return_policies()
    defaults = ebay_policies.get_current_defaults()
    return jsonify({'policies': data, 'default': defaults.get('return')})

@api_bp.route('/policies/location')
def get_inventory_locations():
    data = ebay_policies.get_inventory_locations()
    defaults = ebay_policies.get_current_defaults()
    return jsonify({'locations': data, 'default': defaults.get('location')})

# --- Job/Queue Endpoints (Detail) ---

@api_bp.route('/job/<job_id>/images')
def get_job_images(job_id):
    """Get list of images in a job folder"""
    qm = current_app.queue_manager
    images = image_service.get_job_images(job_id, qm)
    if images is None:
         return jsonify({'error': 'Job not found'}), 404
    return jsonify({'images': images, 'count': len(images)})

@api_bp.route('/job/<job_id>/image/<filename>')
def serve_job_image(job_id, filename):
    """Serve an image from a job folder"""
    qm = current_app.queue_manager
    path = image_service.get_image_path(job_id, filename, qm)
    if not path:
        return jsonify({'error': 'Image not found'}), 404
    return send_file(path)

@api_bp.route('/tools/photo/save', methods=['POST'])
def save_photo_edits():
    """Save photo edits"""
    qm = current_app.queue_manager
    data = request.json
    job_id = data.get('jobId')
    edits = data.get('edits', {})
    
    result, status = image_service.save_edits(job_id, edits, qm)
    return jsonify(result), status

@api_bp.route('/job/<job_id>/update', methods=['POST'])
def update_job_metadata(job_id):
    """
    Update job metadata (title, price, description) in job.json.
    Optionally starts processing if requested.
    """
    qm = current_app.queue_manager
    data = request.json
    
    # 1. Find the job
    job = qm.get_job_by_id(job_id)
    if not job:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
        
    job_folder = Path(job.folder_path)
    if not job_folder.exists():
        return jsonify({'success': False, 'error': 'Job folder not found'}), 404

    # 2. Update Job Object
    try:
        if 'title' in data: job.user_title = validate_title(data['title'])
        if 'price' in data: job.user_price = str(validate_price(data['price']))
        if 'description' in data: job.user_description = data['description']
        if 'condition' in data: job.user_condition = data['condition']
        
        if 'fulfillmentPolicy' in data:
            if job.job_metadata is None: job.job_metadata = {}
            job.job_metadata['fulfillment_policy'] = data['fulfillmentPolicy']

        if 'scheduled_time' in data:
            job.scheduled_time = data['scheduled_time']

    except ValidationError as e:
        return error_response(e.args[0], 400)
    
    # Save to DB
    qm.save_state()
        
    # 3. Optional: Restart Processing if failed or pending
    if data.get('process_now'):
        # Just retry/start blindly. Logic inside retry_job/start_processing handles state checks.
        # But if we really want to check status first:
        from backend.app.services.queue_manager import JobStatus
        
        # Reset status if retryable or pending
        if job.status in [JobStatus.FAILED, JobStatus.PENDING, JobStatus.COMPLETED]:
             qm.retry_job(job_id)
        
        if not qm.is_processing():
            qm.start_processing()
            
    return jsonify({'success': True, 'message': 'Job updated'})

@api_bp.route('/jobs/bulk-update', methods=['POST'])
def bulk_update_jobs():
    """Batch update multiple jobs"""
    qm = current_app.queue_manager
    data = request.json
    job_ids = data.get('jobIds', [])
    updates = data.get('updates', {})
    
    if not job_ids:
        return jsonify({'success': False, 'error': 'No jobIds provided'}), 400
        
    updated_count = 0
    errors = []
    
    for job_id in job_ids:
        job = qm.get_job_by_id(job_id)
        if not job:
            errors.append(f"Job {job_id} not found")
            continue
            
    for job_id in job_ids:
        job = qm.get_job_by_id(job_id)
        if not job:
            errors.append(f"Job {job_id} not found")
            continue
            
        # Apply updates
        try:
            if 'condition' in updates: job.user_condition = updates['condition']
            if 'price' in updates: job.user_price = str(validate_price(updates['price']))
            
            # If "Reset Status" is requested (e.g. to retry)
            if updates.get('reset_status'):
                 from backend.app.services.queue_manager import JobStatus
                 job.status = JobStatus.PENDING
                 job.error_type = None
                 job.error_message = None
            
            updated_count += 1
            
        except Exception as e:
            errors.append(f"Failed to update {job_id}: {e}")
            
    # Save all changes
    qm.save_state()

    return jsonify({
        'success': True, 
        'count': updated_count,
        'errors': errors
    })

@api_bp.route('/jobs/bulk-delete', methods=['POST'])
def bulk_delete_jobs():
    """Batch delete multiple jobs"""
    qm = current_app.queue_manager
    data = request.json
    job_ids = data.get('jobIds', [])
    
    if not job_ids:
        return jsonify({'success': False, 'error': 'No jobIds provided'}), 400
        
    deleted_count = 0
    errors = []
    
    for job_id in job_ids:
        # Check status before deleting? remove_job handles it.
        if qm.remove_job(job_id):
            deleted_count += 1
        else:
            errors.append(f"Failed to delete {job_id}")
            
    return jsonify({
        'success': True, 
        'count': deleted_count,
        'errors': errors
    })


# --- eBay Listings Endpoints ---

@api_bp.route('/listings/active')
def get_active_listings():
    result, status = ebay_service.get_active_listings()
    return jsonify(result), status

@api_bp.route('/listings/<sku>/details')
def get_listing_details(sku):
    result, status = ebay_service.get_listing_details(sku)
    return jsonify(result), status

@api_bp.route('/listings/<sku>', methods=['PUT', 'POST'])
def update_listing(sku):
    """
    Update listing details (Title, Description, Price, Qty).
    Coordinatess updates to both Inventory Item (Product) and Offer.
    """
    try:
        data = request.json
        results = {}
        
        # 1. Update Product Details (Title, Description) if provided
        if 'title' in data or 'description' in data:
            item_updates = {}
            if 'title' in data: item_updates['title'] = data['title']
            if 'description' in data: item_updates['description'] = data['description']
            
            res, status = ebay_service.update_inventory_item(sku, item_updates)
            if status not in [200, 204]:
                return jsonify({'error': 'Failed to update item details', 'details': res}), status
            results['item_update'] = 'success'

        # 2. Update Offer Details (Price, Quantity) if provided
        if 'price' in data or 'quantity' in data:
            updates = [{
                'sku': sku,
                'offerId': data.get('offerId'),
                'price': data.get('price'),
                'quantity': data.get('quantity')
            }]
            res, status = ebay_service.bulk_update(updates)
            if status not in [200, 204]:
                return jsonify({'error': 'Failed to update price/qty', 'details': res}), status
            results['offer_update'] = 'success'
            
        return jsonify({'success': True, 'results': results}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/listings/bulk', methods=['POST'])
def bulk_update_listings():
    data = request.json
    updates = data.get('updates', [])
    if not updates:
         return jsonify({'success': False, 'error': 'No updates provided'}), 400
    
    result, status = ebay_service.bulk_update(updates)
    return jsonify(result), status

@api_bp.route('/listings/<offer_id>/withdraw', methods=['POST'])
def withdraw_listing(offer_id):
    result, status = ebay_service.withdraw_listing(offer_id)
    return jsonify(result), status

@api_bp.route('/listings/<offer_id>/publish', methods=['POST'])
def publish_listing(offer_id):
    result, status = ebay_service.publish_listing(offer_id)
    return jsonify(result), status

@api_bp.route('/listings/bulk/title', methods=['POST'])
def bulk_update_titles():
    data = request.json
    updates = data.get('updates', [])
    if not updates:
        return jsonify({'success': False, 'error': 'No updates provided'}), 400
    
    result, status = ebay_service.bulk_update_titles(updates)
    return jsonify(result), status

# --- Book Scanner Endpoint ---

@api_bp.route('/lookup/book', methods=['GET'])
def lookup_book():
    """
    Lookup book details and market price by ISBN.
    Returns format compatible with frontend QuickListingForm.
    """
    isbn = request.args.get('isbn')
    if not isbn:
        return jsonify({"error": "ISBN is required"}), 400
        
    # Clean ISBN (remove dashes)
    isbn_clean = isbn.replace('-', '').strip()
    logger.info(f"🔍 Lookup Book: {isbn_clean}")
    
    try:
        # 1. Fetch Metadata
        from backend.app.services.book_service import BookService
        book_service = BookService()
        book_data = book_service.lookup_isbn(isbn_clean)
        
        if not book_data.get('success'):
            return jsonify({"error": "Book not found", "details": book_data.get('error')}), 404
            
        # 2. Estimate Price (with ISBN search)
        from backend.app.services.pricing_engine import PricingEngine
        pricing_engine = PricingEngine()
        
        # Build search title
        title = book_data.get('title', '')
        authors = ", ".join(book_data.get('authors', []))
        search_title = f"{title} {authors}"
        
        price_data = pricing_engine.get_price_with_comps(
            title=search_title,
            condition="Used - Good", # Default for books
            isbn=isbn_clean
        )
        
        # 3. Construct Response
        response = {
            "success": True,
            "title": f"{title} by {authors}",
            "item_specifics": {
                "Author": authors,
                "Publisher": book_data.get('publisher'),
                "Publication Year": book_data.get('publishedDate', '')[:4],
                "Book Title": title,
                "Language": "English",
                "Format": "Paperback", # TODO: Infer from Google Books if available?
                "ISBN": isbn_clean
            },
            "description": f"<h2>{title}</h2><p><b>Author:</b> {authors}<br><b>Publisher:</b> {book_data.get('publisher')}<br><b>Year:</b> {book_data.get('publishedDate')}</p><p>{book_data.get('description', '')}</p>",
            "category_id": "267", # Books > TEXTBOOKS, EDUCATION (Generic fallback)
            "price": price_data.get('suggested_price'),
            "pricing_data": price_data,
            "stock_photo": book_data.get('thumbnail')
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"❌ Book lookup failed: {e}")
        return jsonify({"error": str(e)}), 500

# --- Analytics Endpoints ---

@api_bp.route('/sales/recent')
def get_recent_sales():
    result, status = ebay_service.get_recent_sales()
    return jsonify(result), status

@api_bp.route('/analytics/summary')
def get_analytics_summary():
    days = request.args.get('days', 30)
    result, status = ebay_service.get_analytics_summary(days=days)
    return jsonify(result), status

@api_bp.route('/analytics/orders')
def get_analytics_orders():
    days = request.args.get('days', 30)
    limit = request.args.get('limit', 50)
    result, status = ebay_service.get_recent_orders(days=days, limit=limit)
    return jsonify(result), status

# --- Tools Endpoints ---

@api_bp.route('/tools/research')
def search_prices():
    """Price research endpoint"""
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query required'}), 400
        
    # Lazy load to avoid circular imports or heavy init at startup
    from backend.app.services.ebay.researcher import eBayResearcher
    researcher = eBayResearcher()
    
    result = researcher.search_sold(query)
    return jsonify(result)

# --- Application Settings ---

@api_bp.route('/settings', methods=['GET'])
def get_app_settings():
    """Get all application settings from .env"""
    settings_manager = get_settings_manager()
    return jsonify(settings_manager.get_all())

@api_bp.route('/settings', methods=['POST'])
def save_app_settings():
    """Save application settings to .env"""
    settings_manager = get_settings_manager()
    data = request.json
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
        
    try:
        settings_manager.save(data)
        return jsonify({'success': True, 'message': 'Settings saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
