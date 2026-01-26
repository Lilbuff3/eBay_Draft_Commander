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
        # self.trading_service = TradingService() # Deprecated
        self.inventory_service = InventoryService()
        self.inventory_service = InventoryService()
        # Pass a lambda to resolve circular dependency for active count
        self.analytics_service = AnalyticsService(
            inventory_service_callback=lambda: self.get_active_listings()[0]
        )

    # --- Connection Check --- 
    
    def check_connection_status(self):
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

    def get_active_listings(self):
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
    def update_inventory_item(self, sku, update_data):
        return self.inventory_service.update_inventory_item(sku, update_data)
