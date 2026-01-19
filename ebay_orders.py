
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from ebay_auth import eBayOAuth

class eBayOrders:
    """
    Client for eBay Fulfillment API (Orders).
    Used for retrieving sales history and calculating analytics.
    """
    
    BASE_URL_PROD = "https://api.ebay.com/sell/fulfillment/v1/order"
    BASE_URL_SANDBOX = "https://api.sandbox.ebay.com/sell/fulfillment/v1/order"
    
    def __init__(self, use_sandbox=False):
        self.use_sandbox = use_sandbox
        self.base_url = self.BASE_URL_SANDBOX if use_sandbox else self.BASE_URL_PROD
        self.oauth = eBayOAuth(use_sandbox=use_sandbox)
        
    def _get_headers(self):
        """Get authorized headers"""
        if not self.oauth.has_valid_token():
            print("Warning: No valid token, attempting refresh...")
            if not self.oauth.refresh_access_token():
                raise Exception("Authentication failed. Please run functionality requiring auth via CLI first.")
                
        return {
            'Authorization': f'Bearer {self.oauth.user_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def get_orders(self, days_back=90, limit=50) -> Dict:
        """
        Fetch orders from the last N days.
        """
        try:
            headers = self._get_headers()
            
            # Date filter (last N days)
            start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            params = {
                'filter': f'creationdate:[{start_date}..]',
                'limit': limit,
                'offset': 0
            }
            
            response = requests.get(self.base_url, headers=headers, params=params)
            
            if response.status_code != 200:
                print(f"Error fetching orders: {response.status_code} - {response.text}")
                return {'orders': [], 'total': 0, 'error': response.text}
                
            data = response.json()
            return {
                'orders': data.get('orders', []),
                'total': data.get('total', 0)
            }
            
        except Exception as e:
            print(f"Exception in get_orders: {e}")
            return {'orders': [], 'total': 0, 'error': str(e)}

    def get_sales_stats(self, days_back=30):
        """
        Calculate sales statistics for the given period.
        """
        result = self.get_orders(days_back=days_back, limit=200) # maximize limit for stats
        orders = result.get('orders', [])
        
        total_revenue = 0.0
        total_items_sold = 0
        orders_count = len(orders)
        
        daily_sales = {}
        
        # Determine date range for charts
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Initialize daily_sales with 0 for all days
        current_day = start_date
        while current_day <= end_date:
            day_str = current_day.strftime('%Y-%m-%d')
            daily_sales[day_str] = 0.0
            current_day += timedelta(days=1)

        best_sellers = {}

        for order in orders:
            # Parse amounts
            try:
                # Total amount paid by buyer (including tax/shipping)
                total_amount = float(order.get('pricingSummary', {}).get('total', {}).get('value', 0))
                
                # We typically want "Net Sales" (Item Price + Shipping - Tax), but API gives Total (inc tax).
                tax_amount = float(order.get('pricingSummary', {}).get('tax', {}).get('value', 0))
                revenue = total_amount - tax_amount
                
                total_revenue += revenue
                
                # Count items
                for line_item in order.get('lineItems', []):
                    qty = int(line_item.get('quantity', 1))
                    total_items_sold += qty
                    
                    # Track best sellers
                    title = line_item.get('title', 'Unknown Item')
                    if title in best_sellers:
                        best_sellers[title]['qty'] += qty
                        best_sellers[title]['revenue'] += float(line_item.get('total', {}).get('value', 0))
                    else:
                        best_sellers[title] = {
                            'title': title,
                            'qty': qty,
                            'revenue': float(line_item.get('total', {}).get('value', 0))
                        }
                
                # Daily breakdown
                creation_date = order.get('creationDate')
                if creation_date:
                    date_str = creation_date.split('T')[0]
                    if date_str in daily_sales:
                        daily_sales[date_str] += revenue
                        
            except (ValueError, TypeError) as e:
                print(f"Error parsing order data: {e}")
                continue

        # Convert daily_sales to list for charts
        chart_data = [{'date': date, 'sales': amount} for date, amount in daily_sales.items()]
        chart_data.sort(key=lambda x: x['date'])
        
        # Sort best sellers
        top_items = sorted(best_sellers.values(), key=lambda x: x['qty'], reverse=True)[:5]

        # Sell-through Rate Calculation
        # Sell-through = Items Sold / (Items Sold + Active Listings) * 100
        active_listings_count = 0
        try:
            from ebay_policies import _get_headers
            import requests as req_lib
            inv_response = req_lib.get(
                'https://api.ebay.com/sell/inventory/v1/offer',
                headers=_get_headers(),
                params={'marketplace_id': 'EBAY_US', 'limit': 1}  # We only need total count
            )
            if inv_response.status_code == 200:
                active_listings_count = inv_response.json().get('total', 0)
        except Exception as e:
            print(f"Could not fetch active listings for sell-through: {e}")
        
        sell_through_rate = 0.0
        if (total_items_sold + active_listings_count) > 0:
            sell_through_rate = round((total_items_sold / (total_items_sold + active_listings_count)) * 100, 1)

        return {
            'total_revenue': round(total_revenue, 2),
            'orders_count': orders_count,
            'items_sold': total_items_sold,
            'average_order_value': round(total_revenue / orders_count, 2) if orders_count > 0 else 0,
            'chart_data': chart_data,
            'best_sellers': top_items,
            'active_listings_count': active_listings_count,
            'sell_through_rate': sell_through_rate
        }

if __name__ == "__main__":
    # Test
    print("Testing eBay Orders API...")
    client = eBayOrders()
    stats = client.get_sales_stats(days_back=90)
    print(json.dumps(stats, indent=2))
