import requests
from backend.app.core.logger import get_logger
from backend.app.services.ebay.policies import _get_headers, _refresh_token_if_needed

logger = get_logger('ebay_inventory_service')

class InventoryService:
    """Service for handling eBay Inventory API (REST) interactions"""

    def get_inventory_items(self):
        """Fetch active listings from eBay Inventory API"""
        try:
            INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
            
            response = requests.get(
                f'{INVENTORY_URL}/inventory_item',
                headers=_get_headers(),
                params={'limit': 100, 'offset': 0}
            )
            
            if response.status_code in [401, 500] and _refresh_token_if_needed(response):
                response = requests.get(
                    f'{INVENTORY_URL}/inventory_item',
                    headers=_get_headers(),
                    params={'limit': 100, 'offset': 0}
                )
            
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
            response = requests.get(
                f'{INVENTORY_URL}/offer/{offer_id}',
                headers=_get_headers(),
                timeout=10
            )
            
            if response.status_code in [401, 500] and _refresh_token_if_needed(response):
                response = requests.get(
                    f'{INVENTORY_URL}/offer/{offer_id}',
                    headers=_get_headers(),
                    timeout=10
                )
            
            if response.status_code == 200:
                return response.json(), 200
            
            return {'error': f'eBay Offer Error: {response.text}'}, response.status_code
            
        except Exception as e:
            return {'error': str(e)}, 500

    def get_listing_details(self, sku):
        """Fetch details for a single SKU (Offer + Product Description)"""
        try:
            # 1. Fetch Offer (Price, Qty, ListingId)
            INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
            response = requests.get(
                f'{INVENTORY_URL}/offer',
                headers=_get_headers(),
                params={'sku': sku},
                timeout=10
            )
            
            if response.status_code in [401, 500] and _refresh_token_if_needed(response):
                response = requests.get(
                    f'{INVENTORY_URL}/offer',
                    headers=_get_headers(),
                    params={'sku': sku},
                    timeout=10
                )
            
            result_data = {}
            if response.status_code == 200:
                data = response.json()
                offers = data.get('offers', [])
                if offers:
                    offer = offers[0]
                    price_obj = offer.get('pricingSummary', {}).get('price', {})
                    result_data = {
                        'price': float(price_obj.get('value', 0)),
                        'currency': price_obj.get('currency', 'USD'),
                        'quantity': offer.get('availableQuantity', 0),
                        'offerId': offer.get('offerId'),
                        'listingId': offer.get('listingId'),
                        'status': offer.get('status')
                    }
                else:
                    return {'error': 'No offer found for SKU'}, 404
            else:
                return {'error': f'eBay API error (Offer): {response.status_code}'}, 502

            # 2. Fetch Inventory Item (Title, Description)
            item_data, item_status = self.get_inventory_item(sku)
            if item_status == 200:
                product = item_data.get('product', {})
                result_data['title'] = product.get('title')
                result_data['description'] = product.get('description')
                # Add images if we want them later
            
            return result_data, 200
                
        except Exception as e:
            return {'error': str(e)}, 500

    def bulk_update(self, updates):
        """Execute bulk_update_price_quantity"""
        INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
        payload_requests = []
        
        for up in updates:
            req = {'sku': up['sku']}
            if 'quantity' in up and up['quantity'] is not None:
                 req['shipToLocationAvailability'] = {'quantity': int(up['quantity'])}
            if 'price' in up and up['price'] is not None and up.get('offerId'):
                req['offers'] = [{
                    'offerId': up['offerId'],
                    'price': {
                        'value': str(up['price']),
                        'currency': up.get('currency', 'USD')
                    }
                }]
            payload_requests.append(req)
            
        if not payload_requests:
            return {'success': True, 'message': 'No valid updates found'}, 200

        response = requests.post(
            f'{INVENTORY_URL}/bulk_update_price_quantity',
            headers=_get_headers(),
            json={'requests': payload_requests}
        )
        
        if response.status_code in [401, 500]:
            if _refresh_token_if_needed(response):
                 response = requests.post(
                    f'{INVENTORY_URL}/bulk_update_price_quantity',
                    headers=_get_headers(),
                    json={'requests': payload_requests}
                )
        
        if response.status_code != 200:
             return {'error': f"eBay Update Failed: {response.text}"}, 500
             
        res_data = response.json()
        failures = [
            r for r in res_data.get('responses', []) 
            if r.get('statusCode') not in [200, 204]
        ]
        
        if failures:
             return {
                 'success': False, 
                 'message': 'Some updates failed', 
                 'failures': failures,
                 'details': res_data
             }, 207
        
        return {'success': True, 'updated': len(payload_requests)}, 200

    def withdraw_listing(self, offer_id):
        INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
        response = requests.post(f'{INVENTORY_URL}/offer/{offer_id}/withdraw', headers=_get_headers())
        
        if response.status_code in [401, 500]:
             if _refresh_token_if_needed(response):
                response = requests.post(f'{INVENTORY_URL}/offer/{offer_id}/withdraw', headers=_get_headers())
        
        if response.status_code in [200, 204]:
             return {'success': True, 'offerId': offer_id}, 200
        return {'error': response.text}, response.status_code

    def publish_listing(self, offer_id):
        INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
        response = requests.post(f'{INVENTORY_URL}/offer/{offer_id}/publish', headers=_get_headers())
        
        if response.status_code in [401, 500]:
             if _refresh_token_if_needed(response):
                response = requests.post(f'{INVENTORY_URL}/offer/{offer_id}/publish', headers=_get_headers())
        
        if response.status_code in [200, 204]:
             result = response.json()
             return {'success': True, 'listingId': result.get('listingId')}, 200
        return {'error': response.text}, response.status_code

    def bulk_update_titles(self, updates):
        INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
        results = {'success': [], 'failed': []}
        
        for update in updates:
            offer_id = update.get('offerId')
            new_title = update.get('title')
            
            try:
                # GET offer
                get_response = requests.get(f'{INVENTORY_URL}/offer/{offer_id}', headers=_get_headers())
                if get_response.status_code == 401 and _refresh_token_if_needed(get_response):
                     get_response = requests.get(f'{INVENTORY_URL}/offer/{offer_id}', headers=_get_headers())
                
                if get_response.status_code != 200:
                    results['failed'].append({'offerId': offer_id, 'error': f'GET failed: {get_response.status_code}'})
                    continue
                
                offer_data = get_response.json()
                if 'listing' not in offer_data: offer_data['listing'] = {}
                offer_data['listing']['listingTitle'] = new_title
                
                # PUT offer
                put_response = requests.put(f'{INVENTORY_URL}/offer/{offer_id}', headers=_get_headers(), json=offer_data)
                if put_response.status_code == 401 and _refresh_token_if_needed(put_response):
                    put_response = requests.put(f'{INVENTORY_URL}/offer/{offer_id}', headers=_get_headers(), json=offer_data)
                
                if put_response.status_code in [200, 204]:
                    results['success'].append({'offerId': offer_id, 'title': new_title})
                else:
                    results['failed'].append({'offerId': offer_id, 'error': put_response.text[:200]})
            except Exception as e:
                results['failed'].append({'offerId': offer_id, 'error': str(e)})
        
        return {
            'success': len(results['failed']) == 0,
            'updated': len(results['success']),
            'failed': len(results['failed']),
            'details': results
        }, 200
    def get_inventory_item(self, sku):
        """Fetch single inventory item raw data"""
        try:
            INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
            response = requests.get(
                f'{INVENTORY_URL}/inventory_item/{sku}',
                headers=_get_headers()
            )
            
            if response.status_code in [401, 500] and _refresh_token_if_needed(response):
                response = requests.get(
                    f'{INVENTORY_URL}/inventory_item/{sku}',
                    headers=_get_headers()
                )
                
            if response.status_code == 200:
                return response.json(), 200
            return {'error': f'eBay API error: {response.status_code}', 'details': response.text}, response.status_code
            
        except Exception as e:
            logger.exception(f"Error fetching inventory item {sku}")
            return {'error': str(e)}, 500

    def update_inventory_item(self, sku, update_data):
        """
        Update inventory item details (Title, Description).
        This performs a GET -> MERGE -> PUT to ensure we don't wipe existing data.
        """
        # 1. Fetch existing
        current_data, status = self.get_inventory_item(sku)
        if status != 200:
            return current_data, status
            
        # 2. Merge updates
        product = current_data.get('product', {})
        
        if 'title' in update_data:
            product['title'] = update_data['title']
        if 'description' in update_data:
            product['description'] = update_data['description']
        # Add other product fields here if needed (images, aspects)
        
        current_data['product'] = product
        
        # 3. PUT update
        INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
        try:
            response = requests.put(
                f'{INVENTORY_URL}/inventory_item/{sku}',
                headers=_get_headers(),
                json=current_data
            )
            
            if response.status_code in [401, 500] and _refresh_token_if_needed(response):
                response = requests.put(
                    f'{INVENTORY_URL}/inventory_item/{sku}',
                    headers=_get_headers(),
                    json=current_data
                )
                
            if response.status_code in [200, 204]:
                return {'success': True}, 200
            
            return {'error': f'Update failed: {response.status_code}', 'details': response.text}, response.status_code
            
        except Exception as e:
            logger.exception(f"Error updating inventory item {sku}")
            return {'error': str(e)}, 500

    def create_inventory_item(self, sku, item_data):
        """
        Create or Replace an Inventory Item record.
        PUT /sell/inventory/v1/inventory_item/{sku}
        """
        INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
        try:
            logger.info(f"Creating Inventory Item: {sku}")
            response = requests.put(
                f'{INVENTORY_URL}/inventory_item/{sku}',
                headers=_get_headers(),
                json=item_data
            )
            
            if response.status_code in [401, 500] and _refresh_token_if_needed(response):
                response = requests.put(
                    f'{INVENTORY_URL}/inventory_item/{sku}',
                    headers=_get_headers(),
                    json=item_data
                )
                
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
            response = requests.post(
                f'{INVENTORY_URL}/offer',
                headers=_get_headers(),
                json=offer_data
            )
            
            if response.status_code in [401, 500] and _refresh_token_if_needed(response):
                response = requests.post(
                    f'{INVENTORY_URL}/offer',
                    headers=_get_headers(),
                    json=offer_data
                )
                
            if response.status_code in [200, 201]:
                result = response.json()
                return {'success': True, 'offerId': result.get('offerId')}, 200
            
            return {'error': f'Create Offer Failed: {response.status_code}', 'details': response.text}, response.status_code
            
        except Exception as e:
            logger.exception("Error creating offer")
            return {'error': str(e)}, 500
