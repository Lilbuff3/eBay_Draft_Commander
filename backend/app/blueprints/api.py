from flask import Blueprint, jsonify, request, current_app, send_file
from werkzeug.utils import secure_filename
import os
import uuid
import time
from pathlib import Path
from backend.app.services.ebay_service import eBayService
from backend.app.services.image_service import ImageService
from backend.app.services.ebay import policies as ebay_policies    

api_bp = Blueprint('api', __name__)
ebay_service = eBayService()
image_service = ImageService()

# --- Upload Endpoint (Mobile Support) ---

@api_bp.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads from mobile/web and create a new job"""
    if 'files[]' not in request.files:
        return jsonify({'success': False, 'error': 'No files provided'}), 400
        
    files = request.files.getlist('files[]')
    if not files:
        return jsonify({'success': False, 'error': 'No files selected'}), 400
        
    qm = current_app.queue_manager
    
    # Create a unique folder for this upload
    # Using timestamp + short UUID for uniqueness
    folder_name = f"mobile_upload_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    
    # Determine inbox path (using qm.base_path parent or config default)
    # Assuming standard project structure: backend/../inbox
    # But safer to ask Config or use a known relative path
    try:
        # Try to find 'inbox' in project root
        root_dir = Path(current_app.root_path).parent.parent # backend/app -> backend -> root
        inbox_dir = root_dir / 'inbox'
        inbox_dir.mkdir(exist_ok=True)
    except Exception:
        # Fallback to 'uploads' in current directory if structure differs
        inbox_dir = Path('uploads')
        inbox_dir.mkdir(exist_ok=True)

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
        try:
            root_dir = Path(current_app.root_path).parent.parent 
            inbox_dir = root_dir / 'inbox'
            inbox_dir.mkdir(exist_ok=True)
        except:
            inbox_dir = Path('uploads')
            inbox_dir.mkdir(exist_ok=True)
            
        job_folder = inbox_dir / folder_name
        job_folder.mkdir(exist_ok=True)
        
        saved_count = 0
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(str(job_folder / filename))
                saved_count += 1
                
        # 2. Handle Metadata
        import json
        metadata = {
            'user_title': request.form.get('itemName'),
            'user_price': request.form.get('price'),
            'user_description': request.form.get('description'),
            'created_at': time.time()
        }
        
        # Save metadata to job.json so AI can use it
        with open(job_folder / 'job.json', 'w') as f:
            json.dump(metadata, f)
            
        # 3. Queue Job
        job = qm.add_folder(str(job_folder))
        
        # Auto-start processing if idle
        if not qm.is_processing():
            qm.start_processing()
            
        return jsonify({
            'success': True,
            'jobId': job.id,
            'message': 'Listing created and queued for processing'
        })
        
    except Exception as e:
        print(f"Error in create-from-photos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# --- Scanner Endpoint ---

@api_bp.route('/scan', methods=['POST'])
def scan_inbox_endpoint():
    """Trigger scan of inbox directory"""
    try:
        from backend.app.services.scanner_service import ScannerService
        
        # Use config INBOX_DIR or fallback
        inbox_dir = current_app.config.get('INBOX_DIR')
        if not inbox_dir:
            # Fallback (should be set in config)
            inbox_dir = Path(current_app.root_path).parent.parent / 'inbox'
            
        scanner = ScannerService(inbox_dir)
        qm = current_app.queue_manager
        
        result = scanner.scan_inbox(qm)
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
                'error_type': getattr(j, 'error_type', None)
            })
    return jsonify(jobs_data)

@api_bp.route('/start', methods=['POST'])
def start_queue():
    qm = current_app.queue_manager
    qm.start_processing()
    return jsonify({'success': True})

@api_bp.route('/pause', methods=['POST'])
def pause_queue():
    qm = current_app.queue_manager
    qm.pause_processing()
    return jsonify({'success': True})

@api_bp.route('/resume', methods=['POST'])
def resume_queue():
    qm = current_app.queue_manager
    qm.resume_processing()
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
    print(f"🔍 Lookup Book: {isbn_clean}")
    
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
        print(f"❌ Book lookup failed: {e}")
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
