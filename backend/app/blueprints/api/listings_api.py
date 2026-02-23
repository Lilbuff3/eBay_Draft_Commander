from flask import Blueprint, jsonify, request
from backend.app.services.ebay_service import eBayService
from backend.app.services.ebay import policies as ebay_policies
from backend.app.core.logger import get_logger

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

@listings_bp.route('/listings/<sku>', methods=['PUT', 'POST'])
def update_listing(sku):
    """
    Update listing details (Title, Description, Price, Qty).
    Coordinatess updates to both Inventory Item (Product) and Offer.
    """
    try:
        data = request.json
        results = {}
        if 'title' in data or 'description' in data:
            item_updates = {}
            if 'title' in data: item_updates['title'] = data['title']
            if 'description' in data: item_updates['description'] = data['description']
            res, status = ebay_service.update_inventory_item(sku, item_updates)
            if status not in [200, 204]: return jsonify({'error': 'Failed to update item details', 'details': res}), status
            results['item_update'] = 'success'
        if 'price' in data or 'quantity' in data:
            updates = [{
                'sku': sku, 'offerId': data.get('offerId'), 'price': data.get('price'), 'quantity': data.get('quantity')
            }]
            res, status = ebay_service.bulk_update(updates)
            if status not in [200, 204]: return jsonify({'error': 'Failed to update price/qty', 'details': res}), status
            results['offer_update'] = 'success'
        return jsonify({'success': True, 'results': results}), 200
    except Exception as e: return jsonify({'error': str(e)}), 500

@listings_bp.route('/listings/bulk', methods=['POST'])
def bulk_update_listings():
    data = request.json
    updates = data.get('updates', [])
    if not updates: return jsonify({'success': False, 'error': 'No updates provided'}), 400
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
    updates = data.get('updates', [])
    if not updates: return jsonify({'success': False, 'error': 'No updates provided'}), 400
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
