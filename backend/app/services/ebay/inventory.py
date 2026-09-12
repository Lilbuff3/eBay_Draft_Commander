import requests
from backend.app.core.logger import get_logger
from backend.app.services.ebay.policies import _get_headers, _refresh_token_if_needed, ebay_request

logger = get_logger('ebay_inventory_service')

class InventoryService:
    """Service for handling eBay Inventory API (REST) interactions"""

    def get_inventory_items(self):
        """Fetch active listings from eBay Inventory API"""
        try:
            INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
            
            response = ebay_request('GET', f'{INVENTORY_URL}/inventory_item', params={'limit': 100, 'offset': 0})
            
            if response.status_code != 200:
                # GRACEFUL FALLBACK: If 401 (Unauthorized) persists, return empty list (Offline Mode)
                # This allow the UI to load existing local features without crashing.
                if response.status_code == 401:
                    logger.warning("eBay API Unauthorized - Returning Empty Inventory (Offline Mode)")
                    return {
                        'listings': [],
                        'total': 0,
                        'source': 'Offline Mode (Auth Failed)',
                        'status': 'offline' 
                    }, 200
                
                return {'error': f'eBay API error: {response.status_code}'}, 502

            data = response.json()
            items = []
            
            for item in data.get('inventoryItems', []):
                product = item.get('product', {})
                img_urls = product.get('imageUrls', [])
                main_image = img_urls[0] if img_urls else None
                
                items.append({
                    'sku': item.get('sku'),
                    'offerId': None,
                    'listingId': 'Unknown', 
                    'title': product.get('title', 'No Title'),
                    'price': 0.0,
                    'currency': 'USD',
                    'availableQuantity': item.get('availability', {}).get('shipToLocationAvailability', {}).get('quantity', 0),
                    'imageUrl': main_image,
                    'status': 'Active' if item.get('condition') else 'Draft',
                    'condition': item.get('condition', 'USED_EXCELLENT')
                })

            # FALLBACK: If Inventory API returns 0 items, try Legacy Trading API
            if not items:
                logger.info("Inventory API return 0 items. Attempting Legacy Trading API fallback...")
                try:
                    from backend.app.services.ebay.trading import TradingService
                    trading_service = TradingService()
                    legacy_data, status = trading_service.get_active_listings_light()
                    
                    if status == 200:
                         logger.info(f"Legacy Trading API found {len(legacy_data.get('listings', []))} items")
                         return legacy_data, 200
                    else:
                         logger.warning(f"Legacy Trading API failed or found 0 items: {status}")
                except Exception as e:
                    logger.error(f"Legacy Trading API Fallback Error: {e}")
            
            return {
                'listings': items,
                'total': data.get('total', len(items)),
                'source': 'eBay Inventory API'
            }, 200
            
        except Exception as e:
            logger.exception("Inventory API Error")
            # Return empty on crash too? Maybe safer for now to be explicit about errors
            # But user wants "tool to work". Let's stick to catching the specific 401 for now.
            return {'error': str(e)}, 500

    def get_offer(self, offer_id):
        """Fetch details for a specific Offer ID"""
        try:
            INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
            response = ebay_request('GET', f'{INVENTORY_URL}/offer/{offer_id}', timeout=10)
            
            if response.status_code == 200:
                return response.json(), 200
            
            return {'error': f'eBay Offer Error: {response.text}'}, response.status_code
            
        except Exception as e:
            return {'error': str(e)}, 500

    def withdraw_listing(self, offer_id):
        INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
        response = ebay_request('POST', f'{INVENTORY_URL}/offer/{offer_id}/withdraw')
        
        if response.status_code in [200, 204]:
             return {'success': True, 'offerId': offer_id}, 200
        return {'error': response.text}, response.status_code

    def create_inventory_item(self, sku, item_data):
        """
        Create or Replace an Inventory Item record.
        PUT /sell/inventory/v1/inventory_item/{sku}
        """
        INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
        try:
            logger.info(f"Creating Inventory Item: {sku}")
            response = ebay_request('PUT', f'{INVENTORY_URL}/inventory_item/{sku}', json=item_data)
                
            if response.status_code in [200, 204]:
                return {'success': True}, 200
            
            return {'error': f'Create Item Failed: {response.status_code}', 'details': response.text}, response.status_code
            
        except Exception as e:
            logger.exception(f"Error creating inventory item {sku}")
            return {'error': str(e)}, 500

    def create_offer(self, offer_data):
        """
        Create an Offer for an Inventory Item.
        POST /sell/inventory/v1/offer
        """
        INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
        try:
            logger.info(f"Creating Offer for SKU: {offer_data.get('sku')}")
            response = ebay_request('POST', f'{INVENTORY_URL}/offer', json=offer_data)
                
            if response.status_code in [200, 201]:
                result = response.json()
                return {'success': True, 'offerId': result.get('offerId')}, 200
            
            return {'error': f'Create Offer Failed: {response.status_code}', 'details': response.text}, response.status_code
            
        except Exception as e:
            logger.exception("Error creating offer")
            return {'error': str(e)}, 500
