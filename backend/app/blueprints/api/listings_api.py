from flask import Blueprint, jsonify, request, current_app
from backend.app.services.ebay_service import eBayService
from backend.app.services.ebay import policies as ebay_policies
from backend.app.core.logger import get_logger
from backend.app.services.queue_job import JobStatus
from .helpers import error_response

listings_bp = Blueprint('listings', __name__)
logger = get_logger('api.listings')
ebay_service = eBayService()

@listings_bp.route('/ebay/status')
def get_ebay_status():
    """Check eBay API connection status"""
    result, status = ebay_service.check_connection_status()
    return jsonify(result), status

@listings_bp.route('/listings/active')
def get_active_listings():
    result, status = ebay_service.get_active_listings()
    return jsonify(result), status

@listings_bp.route('/listings/<sku>/details')
def get_listing_details(sku):
    result, status = ebay_service.get_listing_details(sku)
    return jsonify(result), status

@listings_bp.route('/listings/<item_id>/price', methods=['POST'])
def revise_listing_price(item_id):
    """Drop/change a live listing's price in place (ReviseFixedPriceItem)."""
    data = request.json or {}
    price = data.get('price')
    if price is None:
        return jsonify({'error': 'price required'}), 400
    result = ebay_service.revise_listing_price(item_id, price, data.get('quantity'))
    return jsonify(result), 200 if result.get('success') else 502

@listings_bp.route('/listings/<item_id>/end', methods=['POST'])
def end_listing_route(item_id):
    """End a live listing by its eBay ItemID."""
    result = ebay_service.end_listing(item_id)
    return jsonify(result), 200 if result.get('success') else 502

@listings_bp.route('/listings/<item_id>/promote', methods=['POST'])
def promote_listing_route(item_id):
    """Promote a listing at the configured ad rate (Promoted Listings)."""
    result = ebay_service.promote_listing(item_id)
    return jsonify(result), 200 if result.get('success') else 502

@listings_bp.route('/listings/<sku>', methods=['PUT', 'POST'])
def update_listing(sku):
    """
    Update listing details (Title, Description, Price, Qty).
    Coordinatess updates to both Inventory Item (Product) and Offer.
    """
    try:
        data = request.json
        if data is None:
            return jsonify({'error': 'Request body must be JSON'}), 400
        results = {}
        if 'title' in data or 'description' in data:
            item_updates = {}
            if 'title' in data: item_updates['title'] = data['title']
            if 'description' in data: item_updates['description'] = data['description']
            res, status = ebay_service.update_inventory_item(sku, item_updates)
            if status not in [200, 204]: return error_response('Failed to update item details', status, details=res)
            results['item_update'] = 'success'
        if 'price' in data or 'quantity' in data:
            updates = [{
                'sku': sku, 'offerId': data.get('offerId'), 'price': data.get('price'), 'quantity': data.get('quantity')
            }]
            res, status = ebay_service.bulk_update(updates)
            if status not in [200, 204]: return error_response('Failed to update price/qty', status, details=res)
            results['offer_update'] = 'success'
        return jsonify({'success': True, 'results': results}), 200
    except Exception as e: return error_response(e)

@listings_bp.route('/listings/bulk', methods=['POST'])
def bulk_update_listings():
    data = request.json
    if data is None:
        return jsonify({'error': 'Request body must be JSON'}), 400
    updates = data.get('updates', [])
    if not updates: return error_response('No updates provided', 400)
    result, status = ebay_service.bulk_update(updates)
    return jsonify(result), status

@listings_bp.route('/listings/<offer_id>/withdraw', methods=['POST'])
def withdraw_listing(offer_id):
    result, status = ebay_service.withdraw_listing(offer_id)
    return jsonify(result), status

@listings_bp.route('/listings/<offer_id>/publish', methods=['POST'])
def publish_listing(offer_id):
    result, status = ebay_service.publish_listing(offer_id)
    return jsonify(result), status

@listings_bp.route('/listings/bulk/title', methods=['POST'])
def bulk_update_titles():
    data = request.json
    if data is None:
        return jsonify({'error': 'Request body must be JSON'}), 400
    updates = data.get('updates', [])
    if not updates: return error_response('No updates provided', 400)
    result, status = ebay_service.bulk_update_titles(updates)
    return jsonify(result), status

@listings_bp.route('/policies/fulfillment')
def get_fulfillment_policies():
    data = ebay_policies.get_fulfillment_policies()
    defaults = ebay_policies.get_current_defaults()
    return jsonify({'policies': data, 'default': defaults.get('fulfillment')})

@listings_bp.route('/policies/payment')
def get_payment_policies():
    data = ebay_policies.get_payment_policies()
    defaults = ebay_policies.get_current_defaults()
    return jsonify({'policies': data, 'default': defaults.get('payment')})

@listings_bp.route('/policies/return')
def get_return_policies():
    data = ebay_policies.get_return_policies()
    defaults = ebay_policies.get_current_defaults()
    return jsonify({'policies': data, 'default': defaults.get('return')})

@listings_bp.route('/policies/location')
def get_inventory_locations():
    data = ebay_policies.get_inventory_locations()
    defaults = ebay_policies.get_current_defaults()
    return jsonify({'locations': data, 'default': defaults.get('location')})

# --- PENDING REVIEW QUEUE ENDPOINTS ---

@listings_bp.route('/listings/pending', methods=['GET'])
def get_pending_listings():
    """Fetch all listings with PENDING_REVIEW status"""
    try:
        queue_manager = getattr(current_app, 'queue_manager', None)
        if not queue_manager:
            return error_response('Queue manager not initialized')

        session = queue_manager.SessionFactory()
        try:
            db_jobs = session.query(queue_manager.JobModel).filter_by(
                status=JobStatus.PENDING_REVIEW.value
            ).all()

            jobs = [queue_manager._db_to_queue_job(j).to_dict() for j in db_jobs]
            return jsonify({'listings': jobs, 'count': len(jobs)}), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to fetch pending listings: {e}")
        return error_response(e)

@listings_bp.route('/listings/<job_id>/quick-edit', methods=['PUT'])
def quick_edit_listing(job_id):
    """Update title, price, and condition for a pending listing"""
    try:
        data = request.json
        if data is None:
            return jsonify({'error': 'Request body must be JSON'}), 400
        queue_manager = getattr(current_app, 'queue_manager', None)
        if not queue_manager:
            return error_response('Queue manager not initialized')

        updates = {}
        if 'title' in data: updates['user_title'] = data['title']
        if 'price' in data: updates['user_price'] = data['price']
        if 'condition' in data: updates['user_condition'] = data['condition']

        if queue_manager.update_job(job_id, updates):
            return jsonify({'success': True}), 200
        else:
            return error_response('Job not found or update failed', 404)
    except Exception as e:
        logger.error(f"Quick edit failed for job {job_id}: {e}")
        return error_response(e)

@listings_bp.route('/listings/batch-approve', methods=['POST'])
def batch_approve_listings():
    """Approve multiple listings and move them back to the active queue"""
    try:
        data = request.json
        if data is None:
            return jsonify({'error': 'Request body must be JSON'}), 400
        job_ids = data.get('listing_ids', [])
        if not job_ids:
            return error_response('No listing IDs provided', 400)

        queue_manager = getattr(current_app, 'queue_manager', None)
        if not queue_manager:
            return error_response('Queue manager not initialized')

        from backend.app.services.review_reply import approve_job
        success_count = sum(
            1 for job_id in job_ids if approve_job(queue_manager, job_id))

        # Trigger queue processing if needed
        if success_count > 0:
            if not queue_manager.is_processing() and not queue_manager.is_paused():
                queue_manager.start_processing()

        return jsonify({'success': True, 'approved_count': success_count}), 200
    except Exception as e:
        logger.error(f"Batch approval failed: {e}")
        return error_response(e)


@listings_bp.route('/review/reply', methods=['POST'])
def review_reply_route():
    """WhatsApp reply-to-review: 'ok' approves, a number sets price+approves,
    'skip' skips. Called by the Hermes capture bridge (loopback)."""
    try:
        data = request.json or {}
        chat_id = (data.get('chat_id') or '').strip()
        text = data.get('text') or ''
        if not chat_id:
            return jsonify({'success': False, 'error': 'chat_id required'}), 400
        queue_manager = getattr(current_app, 'queue_manager', None)
        if not queue_manager:
            return error_response('Queue manager not initialized')

        from backend.app.services.review_reply import apply_review_reply
        result = apply_review_reply(
            queue_manager, chat_id, text,
            captures_dir=current_app.config.get('CAPTURES_DIR'))
        return jsonify(result), (200 if result['success'] else 404)
    except Exception as e:
        logger.error(f"Review reply failed: {e}")
        return error_response(e)
