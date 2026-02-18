from typing import Dict, Any, List, Optional, Tuple, Union
from backend.app.core.logger import get_logger
from backend.app.services.ebay.policies import load_env, _get_headers, _refresh_token_if_needed
import requests

# Import sub-services
from backend.app.services.ebay.trading import TradingService
from backend.app.services.ebay.inventory import InventoryService
from backend.app.services.ebay.analytics import AnalyticsService

logger = get_logger('ebay_service')

class eBayService:
    """
    Facade for eBay Services.
    Delegates functionality to specialized services:
    - TradingService: Legacy XML API (GetSellerList)
    - InventoryService: Modern REST API (Offer/Inventory)
    - AnalyticsService: Orders and Reporting
    """

    def __init__(self):
        self.trading_service = TradingService()
        self.inventory_service = InventoryService()
        # Pass a lambda to resolve circular dependency for active count
        self.analytics_service = AnalyticsService(
            inventory_service_callback=lambda: self.get_active_listings()[0]
        )

    # ... existing methods ...

    # --- Trading API (Classic / Scheduled) ---
    
    def create_trading_api_listing(self, item_data: Dict[str, Any], schedule_time: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a fixed price listing using legacy Trading API (XML).
        Supports scheduling.
        """
        return self.trading_service.add_fixed_price_item(item_data, schedule_time)

    # --- Connection Check --- 
    
    def check_connection_status(self) -> Tuple[Dict[str, str], int]:
    # ... rest of file ...
        """Check if eBay API connection is valid by testing token"""
        try:
            creds = load_env()
            token = creds.get('EBAY_USER_TOKEN')
            
            if not token:
                return {'status': 'disconnected', 'message': 'No eBay token configured'}, 200
            
            # Use Account API to validate token
            ACCOUNT_URL = 'https://api.ebay.com/sell/account/v1'
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.get(
                f'{ACCOUNT_URL}/fulfillment_policy',
                headers=headers,
                params={'marketplace_id': 'EBAY_US'},
                timeout=10
            )
            
            if response.status_code == 200:
                return {'status': 'connected', 'message': 'eBay API token is valid'}, 200
            elif response.status_code == 401:
                if _refresh_token_if_needed(response):
                    return {'status': 'connected', 'message': 'Token refreshed successfully'}, 200
                return {'status': 'expired', 'message': 'eBay token expired'}, 200
            else:
                return {'status': 'error', 'message': f'API returned {response.status_code}'}, 200
                
        except Exception as e:
            logger.exception("Error checking eBay connection")
            return {'status': 'error', 'message': str(e)}, 200

    # --- Listings (Hybrid Strategy) ---

    def get_active_listings(self) -> Tuple[Dict[str, Any], int]:
        """
        Fetch active listings using Inventory API (REST).
        Compliance Note: Legacy Trading API fallback has been removed for 2026 alignment.
        """
        # Exclusively use Inventory API (Sell Feed / Inventory Items)
        return self.inventory_service.get_inventory_items()

    # --- Delegated Methods ---

    def get_listing_details(self, sku):
        return self.inventory_service.get_listing_details(sku)

    def bulk_update(self, updates):
        return self.inventory_service.bulk_update(updates)

    def withdraw_listing(self, offer_id):
        return self.inventory_service.withdraw_listing(offer_id)

    def publish_listing(self, offer_id):
        return self.inventory_service.publish_listing(offer_id)

    def bulk_update_titles(self, updates):
        return self.inventory_service.bulk_update_titles(updates)

    def get_recent_orders(self, days=30, limit=50):
        return self.analytics_service.get_recent_orders(days, limit)

    def get_analytics_summary(self, days=30):
        return self.analytics_service.get_analytics_summary(days)

    def get_recent_sales(self):
        """Deprecated alias"""
        result, status = self.get_recent_orders()
        if status == 200:
             result['period'] = '30 days'
             if 'revenue' not in result:
                 result['revenue'] = sum(o['total'] for o in result['orders'])
        return result, status
    def update_inventory_item(self, sku: str, update_data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        return self.inventory_service.update_inventory_item(sku, update_data)

    def create_listing_bundle(self, sku: str, item_data: Dict[str, Any], offer_data: Dict[str, Any], auto_publish: bool = False) -> Dict[str, Any]:
        """
        Orchestrate the creation of an inventory item and an offer.
        Optionally publishes the offer.
        
        Args:
            sku: The SKU ID
            item_data: Dict for create_inventory_item
            offer_data: Dict for create_offer
            auto_publish: Boolean, whether to publish immediately
            
        Returns:
            Dict with 'listing_id', 'offer_id', 'status', 'success'
        """
        result = {
            'success': False,
            'sku': sku,
            'offer_id': None,
            'listing_id': None,
            'status': 'error',
            'details': []
        }
        
        # 1. Create Inventory Item
        resp, code = self.inventory_service.create_inventory_item(sku, item_data)
        if code not in [200, 204]:
            result['details'].append(f"Item Create Failed: {resp}")
            return result
            
        # 2. Create Offer
        resp, code = self.inventory_service.create_offer(offer_data)
        if code not in [200, 201]:
             result['details'].append(f"Offer Create Failed: {resp}")
             return result
        
        offer_id = resp.get('offerId')
        result['offer_id'] = offer_id
        result['status'] = 'draft'
        result['success'] = True
        
        # 3. Auto-Publish (Optional)
        if auto_publish:
            pub_resp, pub_code = self.publish_listing(offer_id)
            if pub_code == 200:
                result['listing_id'] = pub_resp.get('listingId')
                result['status'] = 'active'
                result['details'].append(f"Published Listing ID: {result['listing_id']}")
            else:
                 result['status'] = 'draft (publish_failed)'
                 result['details'].append(f"Publish Failed: {pub_resp}")
                 
        return result
