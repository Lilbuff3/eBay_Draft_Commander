from flask import Blueprint, jsonify, request, current_app
from backend.app.services.ebay.trading import TradingService
from backend.app.services.ebay.inventory import InventoryService
from backend.app.services.ebay.policies import load_env
from backend.app.core.database import JobModel
from backend.app.core.logger import get_logger
from .helpers import error_response

migration_bp = Blueprint('migration', __name__)
logger = get_logger('api.migration')


@migration_bp.route('/migration/check')
def check_legacy_listings():
    """
    Scan eBay account for active listings and flag which ones
    are already tracked in the local jobs database.

    Returns: { items: [{ listingId, title, price, sku, imageUrl, inInventory }] }
    """
    try:
        trading = TradingService()
        result, status = trading.get_active_listings_light()

        if status == 404:
            return jsonify({'items': [], 'total': 0}), 200

        if status != 200:
            return error_response(
                result.get('error', 'Failed to fetch eBay listings'),
                502
            )

        listings = result.get('listings', [])

        # Get all listing_ids already tracked locally
        tracked_ids = set()
        try:
            queue_manager = getattr(current_app, 'queue_manager', None)
            if queue_manager:
                session = queue_manager.SessionFactory()
                try:
                    rows = session.query(JobModel.listing_id).filter(
                        JobModel.listing_id.isnot(None),
                        JobModel.listing_id != ''
                    ).all()
                    tracked_ids = {r[0] for r in rows}
                finally:
                    session.close()
        except Exception as e:
            logger.warning(f"Could not query local jobs: {e}")

        # Build response matching frontend LegacyItem interface
        items = []
        for listing in listings:
            listing_id = listing.get('listingId', '')
            items.append({
                'listingId': listing_id,
                'title': listing.get('title', 'Untitled'),
                'price': listing.get('price', 0.0),
                'sku': listing.get('sku') or None,
                'imageUrl': listing.get('imageUrl') or None,
                'inInventory': listing_id in tracked_ids,
            })

        return jsonify({'items': items, 'total': len(items)}), 200

    except Exception as e:
        logger.exception("Migration check failed")
        return error_response(str(e))


@migration_bp.route('/migration/execute', methods=['POST'])
def execute_migration():
    """
    Import selected eBay listings into the Inventory API.

    Accepts: { listingIds: string[] }
    Returns: { responses: [{ listingId, statusCode, error? }] }
    """
    try:
        data = request.get_json()
        listing_ids = data.get('listingIds', [])

        if not listing_ids:
            return error_response('No listing IDs provided', 400)

        # Fetch current eBay listings to get full details
        trading = TradingService()
        result, status = trading.get_active_listings_light()

        if status != 200:
            return error_response('Failed to fetch listing details from eBay', 502)

        # Build lookup by listing ID
        listings_by_id = {
            l['listingId']: l for l in result.get('listings', [])
        }

        inventory = InventoryService()
        env = load_env()
        responses = []

        for lid in listing_ids:
            listing = listings_by_id.get(lid)
            if not listing:
                responses.append({
                    'listingId': lid,
                    'statusCode': 404,
                    'error': 'Listing not found on eBay'
                })
                continue

            try:
                # Generate SKU if not present
                import hashlib
                sku = listing.get('sku') or ''
                if not sku or not sku.startswith('DC-'):
                    sku = f"DC-{hashlib.md5(lid.encode()).hexdigest()[:8].upper()}"

                # Create inventory item
                item_payload = {
                    'product': {
                        'title': listing.get('title', 'Untitled'),
                        'imageUrls': [listing['imageUrl']] if listing.get('imageUrl') else [],
                    },
                    'condition': listing.get('condition', 'USED_EXCELLENT'),
                    'availability': {
                        'shipToLocationAvailability': {
                            'quantity': listing.get('availableQuantity', 1)
                        }
                    }
                }

                res, code = inventory.create_inventory_item(sku, item_payload)
                if code not in (200, 204):
                    responses.append({
                        'listingId': lid,
                        'statusCode': code,
                        'error': res.get('error', 'Failed to create inventory item')
                    })
                    continue

                # Create offer linking to existing listing
                offer_payload = {
                    'sku': sku,
                    'marketplaceId': 'EBAY_US',
                    'format': 'FIXED_PRICE',
                    'listingDescription': listing.get('title', ''),
                    'pricingSummary': {
                        'price': {
                            'value': str(listing.get('price', 0)),
                            'currency': 'USD'
                        }
                    },
                    'availableQuantity': listing.get('availableQuantity', 1),
                    'listingPolicies': {
                        'fulfillmentPolicyId': env.get('EBAY_FULFILLMENT_POLICY', ''),
                        'paymentPolicyId': env.get('EBAY_PAYMENT_POLICY', ''),
                        'returnPolicyId': env.get('EBAY_RETURN_POLICY', ''),
                    },
                    'merchantLocationKey': env.get('EBAY_MERCHANT_LOCATION', ''),
                }

                offer_res, offer_code = inventory.create_offer(offer_payload)
                if offer_code in (200, 201):
                    responses.append({'listingId': lid, 'statusCode': 200})
                else:
                    responses.append({
                        'listingId': lid,
                        'statusCode': offer_code,
                        'error': offer_res.get('error', 'Failed to create offer')
                    })

            except Exception as e:
                logger.error(f"Migration failed for listing {lid}: {e}")
                responses.append({
                    'listingId': lid,
                    'statusCode': 500,
                    'error': str(e)
                })

        return jsonify({'responses': responses}), 200

    except Exception as e:
        logger.exception("Migration execute failed")
        return error_response(str(e))
