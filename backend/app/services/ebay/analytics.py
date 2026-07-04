import requests
from datetime import datetime, timedelta
from backend.app.core.logger import get_logger
from backend.app.services.ebay.policies import _get_headers, _refresh_token_if_needed, ebay_request

logger = get_logger('ebay_analytics_service')

class AnalyticsService:
    """Service for handling eBay Analytics and Order data"""
    
    def __init__(self, inventory_service_callback=None):
        self._get_active_count = inventory_service_callback

    def _get_price_value(self, pricing_dict: dict, keys: list = None) -> float:
        """Helper to extract a float value from a variety of eBay price structures"""
        if not pricing_dict:
            return 0.0
        
        # Keys to try in order of preference
        if not keys:
            keys = ['total', 'totalAmount', 'subtotal', 'price', 'amount']
            
        for key in keys:
            val_obj = pricing_dict.get(key)
            if isinstance(val_obj, dict):
                try:
                    return float(val_obj.get('value', 0))
                except (ValueError, TypeError):
                    continue
            elif val_obj is not None:
                try:
                    return float(val_obj)
                except (ValueError, TypeError):
                    continue
                    
        return 0.0

    def get_recent_orders(self, days=30, limit=50):
        """Fetch recent orders from eBay Fulfillment API"""
        try:
            FULFILLMENT_URL = 'https://api.ebay.com/sell/fulfillment/v1'
            date_from = (datetime.now() - timedelta(days=int(days))).strftime('%Y-%m-%dT00:00:00.000Z')
            
            response = ebay_request('GET', f'{FULFILLMENT_URL}/order', params={'filter': f'creationdate:[{date_from}..]', 'limit': limit})
            
            
            if response.status_code != 200:
                return {'error': f'eBay API error: {response.status_code}', 'details': response.text[:200]}, 500
            
            data = response.json()
            orders = []
            
            for order in data.get('orders', []):
                # Use safer extraction
                order_total = self._get_price_value(order.get('pricingSummary'))
                line_items = order.get('lineItems', [])
                first = line_items[0] if line_items else {}
                instructions = first.get('lineItemFulfillmentInstructions') or {}
                payments = (order.get('paymentSummary') or {}).get('payments') or []

                orders.append({
                    'orderId': order.get('orderId'),
                    'creationDate': order.get('creationDate'),
                    'buyer': order.get('buyer', {}).get('username', 'Guest'),
                    'total': order_total,
                    'status': order.get('orderFulfillmentStatus'),
                    'itemCount': len(line_items),
                    'itemTitle': first.get('title'),
                    'legacyItemId': first.get('legacyItemId'),
                    'quantity': first.get('quantity'),
                    'shipByDate': instructions.get('shipByDate'),
                    'paidDate': payments[0].get('paymentDate') if payments else None,
                })
            
            return {
                'orders': orders,
                'total': data.get('total', len(orders)),
                'source': 'eBay Fulfillment API'
            }, 200
        except Exception as e:
            logger.exception("Error getting recent orders")
            return {'error': str(e)}, 500

    def get_analytics_summary(self, days=30):
        """Calculate analytics summary from orders"""
        try:
            # 1. Fetch Orders
            FULFILLMENT_URL = 'https://api.ebay.com/sell/fulfillment/v1'
            date_from = (datetime.now() - timedelta(days=int(days))).strftime('%Y-%m-%dT00:00:00.000Z')
            
            # We need ALL orders for calculation, so increase limit
            response = ebay_request('GET', f'{FULFILLMENT_URL}/order', params={'filter': f'creationdate:[{date_from}..]', 'limit': 200})
            
            
            if response.status_code != 200:
                return {'error': f'eBay API error: {response.status_code}'}, 500
                
            data = response.json()
            orders = data.get('orders', [])
            
            # 2. Calculate Stats
            total_revenue = 0.0
            items_sold = 0
            daily_sales = {}
            item_sales = {} # title -> {qty, revenue}
            
            for order in orders:
                # Revenue - safely extract
                order_total = self._get_price_value(order.get('pricingSummary'))
                total_revenue += order_total
                
                # Date for chart
                date_str = order.get('creationDate')
                if date_str:
                    # Parse "2023-10-27T10:00:00.000Z" -> "2023-10-27"
                    day = date_str.split('T')[0]
                    daily_sales[day] = daily_sales.get(day, 0) + order_total
                
                # Items
                for line_item in order.get('lineItems', []):
                    qty = int(line_item.get('quantity', 1))
                    items_sold += qty
                    title = line_item.get('title', 'Unknown Item')
                    
                    if title not in item_sales:
                        item_sales[title] = {'qty': 0, 'revenue': 0.0}
                    item_sales[title]['qty'] += qty
                    
                    # Line item revenue extraction
                    line_total = self._get_price_value(line_item.get('total'))
                    item_sales[title]['revenue'] += line_total

            # 3. Format Chart Data
            chart_data = []
            # Fill in missing dates? For now just present ones
            for day in sorted(daily_sales.keys()):
                chart_data.append({'date': day, 'sales': round(daily_sales[day], 2)})
                
            # 4. Format Best Sellers
            best_sellers = []
            for title, stats in item_sales.items():
                best_sellers.append({
                    'title': title,
                    'qty': stats['qty'],
                    'revenue': round(stats['revenue'], 2)
                })
            # Sort by revenue desc
            best_sellers.sort(key=lambda x: x['revenue'], reverse=True)
            best_sellers = best_sellers[:5]
            
            # 5. Get Active Listings Count (for sell-through)
            active_count = 0
            if self._get_active_count:
                try:
                    count_res = self._get_active_count()
                    if count_res and isinstance(count_res, dict):
                        active_count = count_res.get('total', 0)
                except Exception as e:
                    logger.warning(f"Failed to get active count via callback: {e}")
            
            # 6. Calculate Averages
            orders_count = len(orders)
            average_order_value = total_revenue / orders_count if orders_count > 0 else 0
            
            sell_through_rate = 0
            total_inventory = items_sold + active_count
            if total_inventory > 0:
                sell_through_rate = round((items_sold / total_inventory) * 100, 1)

            return {
                'total_revenue': round(total_revenue, 2),
                'orders_count': orders_count,
                'items_sold': items_sold,
                'average_order_value': round(average_order_value, 2),
                'chart_data': chart_data,
                'best_sellers': best_sellers,
                'active_listings_count': active_count,
                'sell_through_rate': sell_through_rate
            }, 200

        except Exception as e:
            logger.exception("Error generating analytics summary")
            return {'error': str(e)}, 500
