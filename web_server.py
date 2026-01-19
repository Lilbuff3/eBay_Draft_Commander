"""
Web Control Server for eBay Draft Commander Pro
Provides a mobile-friendly web interface for remote monitoring and control
"""
import os
import io
import socket
import threading
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file, send_from_directory
import requests
import shutil
import uuid
from werkzeug.utils import secure_filename

from logger import get_logger
from exceptions import eBayAPIError, eBayAuthError, eBayTimeoutError, from_http_status

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    from PIL import Image, ImageEnhance
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: Pillow not installed. Photo editing will be disabled.")

from ebay_researcher import eBayResearcher
from template_store import TemplateStore
try:
    from ebay_orders import eBayOrders
except ImportError:
    eBayOrders = None


try:
    import ebay_policies
    HAS_POLICIES = True
except ImportError:
    HAS_POLICIES = False
    print("Warning: ebay_policies not available")


class WebControlServer:
    """Web server for remote control of Draft Commander"""
    
    def __init__(self, queue_manager, port=5000):
        """
        Initialize the web server
        
        Args:
            queue_manager: Reference to the QueueManager instance
            port: Port to run the server on (default 5000)
        """
        self.queue_manager = queue_manager
        self.port = port
        self.host = '0.0.0.0'  # Bind to all interfaces
        self._thread = None
        self._running = False
        
        # Create Flask app
        template_dir = Path(__file__).parent / 'templates'
        static_dir = Path(__file__).parent / 'static'
        
        # Frontend build directory
        self.frontend_dir = Path(__file__).parent / 'frontend' / 'dist'
        
        self.app = Flask(__name__, 
                        template_folder=str(template_dir),
                        static_folder=str(static_dir))
        
        # Disable Flask's default logging in production
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        # Register routes
        self._register_routes()

        # Initialize helpers
        self.researcher = eBayResearcher()
        self.template_store = TemplateStore(self.queue_manager.data_path)
        
        # Initialize logger
        self.logger = get_logger('web_server')
        self.logger.info(f"Initializing web server on port {port}")
        
        self.orders_client = None
        if eBayOrders:
            try:
                self.orders_client = eBayOrders()
            except ImportError as e:
                self.logger.warning(f"Analytics module not available: {e}")
            except Exception as e:
                self.logger.error(f"Analytics client failed to initialize", exc_info=True)

        
    def _register_routes(self):
        """Register all Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main mobile dashboard"""
            return render_template('mobile.html')

        @self.app.route('/modern')
        def modern_dashboard():
            """Legacy React+Tailwind Prototype (archived)"""
            return render_template('modern_dashboard.html')
        
        @self.app.route('/app')
        @self.app.route('/app/<path:path>')
        def serve_vite_app(path=''):
            """Serve the Vite-built React app"""
            app_dir = Path(__file__).parent / 'static' / 'app'
            
            # If path exists as a file, serve it
            if path and (app_dir / path).exists():
                return send_from_directory(app_dir, path)
            # Otherwise serve index.html (for SPA routing)
            return send_from_directory(app_dir, 'index.html')

        # --- Tool API Endpoints ---

        @self.app.route('/api/job/<job_id>/images')
        def get_job_images(job_id):
            """Get list of images in a job folder"""
            job = self.queue_manager.get_job_by_id(job_id)
            if not job:
                return jsonify({'error': 'Job not found'}), 404
            
            folder_path = Path(job.folder_path)
            images = []
            
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp']:
                for img_path in sorted(folder_path.glob(ext)):
                    images.append({
                        'name': img_path.name,
                        'url': f'/api/job/{job_id}/image/{img_path.name}'
                    })
            
            return jsonify({'images': images, 'count': len(images)})

        @self.app.route('/api/job/<job_id>/image/<filename>')
        def serve_job_image(job_id, filename):
            """Serve an image from a job folder"""
            job = self.queue_manager.get_job_by_id(job_id)
            if not job:
                return jsonify({'error': 'Job not found'}), 404
            
            folder_path = Path(job.folder_path)
            image_path = folder_path / filename
            
            if not image_path.exists():
                return jsonify({'error': 'Image not found'}), 404
            
            return send_file(image_path)

        @self.app.route('/api/listings/active')
        def get_active_listings():
            """
            Fetch active listings (Published Offers) from eBay Inventory API.
            Now uses /offer endpoint to get Price and Offer ID.
            """
            try:
                from ebay_policies import load_env, _get_headers, _refresh_token_if_needed
                
                INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
                
                # Get Offers (limit 100 for now, TODO: pagination)
                response = requests.get(
                    f'{INVENTORY_URL}/offer',
                    headers=_get_headers(),
                    params={'marketplace_id': 'EBAY_US', 'limit': 100},
                    timeout=30
                )
                
                # Retry on auth error
                if response.status_code in [401, 500]:
                    if _refresh_token_if_needed(response):
                        response = requests.get(
                            f'{INVENTORY_URL}/offer',
                            headers=_get_headers(),
                            params={'marketplace_id': 'EBAY_US', 'limit': 100},
                            timeout=30
                        )
                
                if response.status_code != 200:
                    self.logger.error(f"eBay Inventory API error: {response.status_code}",
                                    extra={'response': response.text[:500]})
                    return jsonify({'error': f'eBay API error: {response.status_code}'}), 502
                
                data = response.json()
                items = []
                
                for offer in data.get('offers', []):
                    # We return all statuses (PUBLISHED, UNPUBLISHED) so frontend can filter
                    # if offer.get('status') != 'PUBLISHED':
                    #    continue
                        
                    sku = offer.get('sku')
                    listing = offer.get('listing', {})
                    pricing = offer.get('pricingSummary', {})
                    
                    # We assume pricing.price.value exists
                    price_val = pricing.get('price', {}).get('value')
                    
                    items.append({
                        'sku': sku,
                        'offerId': offer.get('offerId'),
                        'listingId': listing.get('listingId'),
                        'title': listing.get('listingTitle') or sku, # Fallback title
                        'price': float(price_val) if price_val else 0.0,
                        'currency': pricing.get('price', {}).get('currency', 'USD'),
                        'availableQuantity': offer.get('availableQuantity', 0),
                        'imageUrl': None, # TODO: Fetch from inventory_item if needed, or Browse API
                        'status': offer.get('status')
                    })
                
                return jsonify({
                    'listings': items,
                    'total': len(items), # This is count of fetched active, not global total
                    'source': 'eBay Inventory Offer API'
                })
                
            except requests.Timeout:
                self.logger.error("eBay Inventory API timeout")
                return jsonify({'error': 'eBay API timeout, please try again'}), 504
                
            except requests.RequestException as e:
                self.logger.exception("eBay Inventory API request failed")
                return jsonify({'error': 'Network error connecting to eBay'}), 503
                
            except ImportError as e:
                self.logger.error(f"Missing ebay_policies module: {e}")
                return jsonify({'error': 'eBay integration not configured'}), 500
                
            except Exception as e:
                self.logger.exception("Unexpected error fetching active listings")
                return jsonify({'error': 'Internal server error'}), 500


        @self.app.route('/api/listings/<sku>', methods=['PUT', 'POST'])
        def update_listing(sku):
            """Update listing price and quantity (Wrapper for bulk update)"""
            try:
                data = request.json
                # We reuse the bulk endpoint logic
                updates = [{
                    'sku': sku,
                    'offerId': data.get('offerId'),
                    'price': data.get('price'),
                    'quantity': data.get('quantity')
                }]
                
                return self._perform_bulk_update(updates)
                
            except (KeyError, ValueError) as e:
                self.logger.warning(f"Invalid update data for SKU {sku}: {e}")
                return jsonify({'error': 'Invalid request data'}), 400
                
            except Exception as e:
                self.logger.exception(f"Error updating listing {sku}")
                return jsonify({'error': 'Failed to update listing'}), 500

        @self.app.route('/api/listings/bulk', methods=['POST'])
        def bulk_update_listings():
            """
            Bulk update Price and Quantity.
            Input: {'updates': [{sku, offerId, price, quantity, currency}, ...]}
            """
            try:
                data = request.json
                updates = data.get('updates', [])
                if not updates:
                     return jsonify({'success': False, 'error': 'No updates provided'}), 400
                
                return self._perform_bulk_update(updates)
                
            except (KeyError, ValueError, TypeError) as e:
                self.logger.warning(f"Invalid bulk update data: {e}")
                return jsonify({'error': 'Invalid request format'}), 400
                
            except Exception as e:
                self.logger.exception("Bulk update failed")
                return jsonify({'error': 'Bulk update failed'}), 500

        def _perform_bulk_update(self, updates):
            """Helper to execute bulk_update_price_quantity"""
            from ebay_policies import _get_headers, _refresh_token_if_needed
            import requests
            
            INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
            
            payload_requests = []
            
            for up in updates:
                req = {'sku': up['sku']}
                
                # Quantity update (shipToLocationAvailability)
                if 'quantity' in up and up['quantity'] is not None:
                     req['shipToLocationAvailability'] = {
                         'quantity': int(up['quantity'])
                     }
                
                # Price update (needs offerId)
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
                return jsonify({'success': True, 'message': 'No valid updates found'})
                
            # Execute Call
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
                 return jsonify({'error': f"eBay Update Failed: {response.text}"}), 500
                 
            # Parse responses (some might fail, some succeed)
            # The API returns {'responses': [{'statusCode': 200, ...}, ...]}
            res_data = response.json()
            failures = [
                r for r in res_data.get('responses', []) 
                if r.get('statusCode') not in [200, 204]
            ]
            
            if failures:
                 return jsonify({
                     'success': False, 
                     'message': 'Some updates failed', 
                     'failures': failures,
                     'details': res_data
                 }), 207  # Partial content-ish
            
            return jsonify({'success': True, 'updated': len(payload_requests)})

        @self.app.route('/api/listings/<offer_id>/withdraw', methods=['POST'])
        def withdraw_listing(offer_id):
            """End a listing (Withdraw Offer)"""
            try:
                from ebay_policies import _get_headers, _refresh_token_if_needed
                import requests
                
                INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
                
                response = requests.post(
                    f'{INVENTORY_URL}/offer/{offer_id}/withdraw',
                    headers=_get_headers()
                )
                
                if response.status_code in [401, 500]:
                     if _refresh_token_if_needed(response):
                        response = requests.post(
                            f'{INVENTORY_URL}/offer/{offer_id}/withdraw',
                            headers=_get_headers()
                        )
                
                # 200 or 204 is success
                if response.status_code in [200, 204]:
                     return jsonify({'success': True, 'offerId': offer_id})
                else:
                     return jsonify({'error': response.text}), response.status_code
                     
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/listings/<offer_id>/publish', methods=['POST'])
        def publish_listing(offer_id):
            """Relist an item (Publish Offer)"""
            try:
                from ebay_policies import _get_headers, _refresh_token_if_needed
                import requests
                
                INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
                
                response = requests.post(
                    f'{INVENTORY_URL}/offer/{offer_id}/publish',
                    headers=_get_headers()
                )
                
                if response.status_code in [401, 500]:
                     if _refresh_token_if_needed(response):
                        response = requests.post(
                            f'{INVENTORY_URL}/offer/{offer_id}/publish',
                            headers=_get_headers()
                        )
                
                if response.status_code in [200, 204]:
                     result = response.json()
                     return jsonify({'success': True, 'listingId': result.get('listingId')})
                else:
                     return jsonify({'error': response.text}), response.status_code
                     
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/listings/bulk/title', methods=['POST'])
        def bulk_update_titles():
            """
            Bulk update listing titles.
            Input: {'updates': [{'offerId': str, 'title': str}, ...]}
            Strategy: Fetch each offer, update title in listing object, PUT back.
            """
            try:
                from ebay_policies import _get_headers, _refresh_token_if_needed
                import requests
                
                INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
                data = request.json
                updates = data.get('updates', [])
                
                if not updates:
                    return jsonify({'success': False, 'error': 'No updates provided'}), 400
                
                results = {'success': [], 'failed': []}
                
                for update in updates:
                    offer_id = update.get('offerId')
                    new_title = update.get('title')
                    
                    if not offer_id or not new_title:
                        results['failed'].append({'offerId': offer_id, 'error': 'Missing offerId or title'})
                        continue
                    
                    try:
                        # Step 1: GET the current offer
                        get_response = requests.get(
                            f'{INVENTORY_URL}/offer/{offer_id}',
                            headers=_get_headers()
                        )
                        
                        if get_response.status_code == 401:
                            if _refresh_token_if_needed(get_response):
                                get_response = requests.get(
                                    f'{INVENTORY_URL}/offer/{offer_id}',
                                    headers=_get_headers()
                                )
                        
                        if get_response.status_code != 200:
                            results['failed'].append({'offerId': offer_id, 'error': f'GET failed: {get_response.status_code}'})
                            continue
                        
                        offer_data = get_response.json()
                        
                        # Step 2: Update the listing title
                        if 'listing' not in offer_data:
                            offer_data['listing'] = {}
                        offer_data['listing']['listingTitle'] = new_title
                        
                        # Step 3: PUT the updated offer
                        put_response = requests.put(
                            f'{INVENTORY_URL}/offer/{offer_id}',
                            headers=_get_headers(),
                            json=offer_data
                        )
                        
                        if put_response.status_code == 401:
                            if _refresh_token_if_needed(put_response):
                                put_response = requests.put(
                                    f'{INVENTORY_URL}/offer/{offer_id}',
                                    headers=_get_headers(),
                                    json=offer_data
                                )
                        
                        if put_response.status_code in [200, 204]:
                            results['success'].append({'offerId': offer_id, 'title': new_title})
                        else:
                            results['failed'].append({'offerId': offer_id, 'error': put_response.text[:200]})
                            
                    except Exception as inner_e:
                        results['failed'].append({'offerId': offer_id, 'error': str(inner_e)})
                
                return jsonify({
                    'success': len(results['failed']) == 0,
                    'updated': len(results['success']),
                    'failed': len(results['failed']),
                    'details': results
                })
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/sales/recent')
        def get_recent_sales():

            """Fetch recent orders from eBay Fulfillment API"""
            try:
                from ebay_policies import load_env, _get_headers, _refresh_token_if_needed
                import requests
                from datetime import datetime, timedelta
                
                FULFILLMENT_URL = 'https://api.ebay.com/sell/fulfillment/v1'
                
                # Get orders from last 30 days
                date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT00:00:00.000Z')
                
                response = requests.get(
                    f'{FULFILLMENT_URL}/order',
                    headers=_get_headers(),
                    params={
                        'filter': f'creationdate:[{date_from}..]',
                        'limit': 50
                    }
                )
                
                # Retry on auth error
                if response.status_code in [401, 500]:
                    if _refresh_token_if_needed(response):
                        response = requests.get(
                            f'{FULFILLMENT_URL}/order',
                            headers=_get_headers(),
                            params={
                                'filter': f'creationdate:[{date_from}..]',
                                'limit': 50
                            }
                        )
                
                if response.status_code != 200:
                    return jsonify({'error': f'eBay API error: {response.status_code}', 'details': response.text[:200]}), 500
                
                data = response.json()
                orders = []
                total_revenue = 0.0
                
                for order in data.get('orders', []):
                    subtotal = float(order.get('pricingSummary', {}).get('total', {}).get('value', 0))
                    total_revenue += subtotal
                    
                    orders.append({
                        'orderId': order.get('orderId'),
                        'creationDate': order.get('creationDate'),
                        'buyer': order.get('buyer', {}).get('username'),
                        'total': subtotal,
                        'status': order.get('orderFulfillmentStatus'),
                        'itemCount': len(order.get('lineItems', []))
                    })
                
                return jsonify({
                    'orders': orders,
                    'total': data.get('total', len(orders)),
                    'revenue': round(total_revenue, 2),
                    'period': '30 days',
                    'source': 'eBay Fulfillment API'
                })
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/tools/photo/save', methods=['POST'])
        def save_photo_edits():
            """Save photo edits"""
            if not HAS_PIL:
                return jsonify({'success': False, 'error': 'Server missing Pillow library'}), 500

            try:
                data = request.json
                job_id = data.get('jobId')
                edits = data.get('edits', {})
                
                # Find the job to get the folder path
                job = self.queue_manager.get_job_by_id(job_id)
                if not job:
                    return jsonify({'success': False, 'error': 'Job not found'}), 404

                # Find the image file (naive implementation: take first jpg/png)
                folder_path = Path(job.folder_path)
                image_files = list(folder_path.glob('*.jpg')) + list(folder_path.glob('*.png'))
                if not image_files:
                    return jsonify({'success': False, 'error': 'No images found in job folder'}), 404
                
                # Use the main image (first name sort) or a specific one if passed
                target_image = sorted(image_files)[0]
                
                # Process with PIL
                with Image.open(target_image) as img:
                    # Rotation
                    rotation = edits.get('rotation', 0)
                    if rotation:
                        img = img.rotate(-rotation, expand=True) # Negative because UI usually goes CW, PIL CCW
                    
                    # Crop (normalized coordinates 0-1)
                    crop = edits.get('crop')
                    if crop:
                        w, h = img.size
                        left = crop['x'] * w / 100
                        top = crop['y'] * h / 100
                        img = img.crop((left, top, left + (crop['width'] * w / 100), top + (crop['height'] * h / 100)))

                    # Adjustments
                    adj = edits.get('adjustments', {})
                    if adj:
                        if 'brightness' in adj:
                            img = ImageEnhance.Brightness(img).enhance(adj['brightness'] / 50.0)
                        if 'contrast' in adj:
                            img = ImageEnhance.Contrast(img).enhance(adj['contrast'] / 50.0)
                        if 'saturation' in adj:
                            img = ImageEnhance.Color(img).enhance(adj['saturation'] / 50.0)
                        if 'sharpness' in adj:
                            img = ImageEnhance.Sharpness(img).enhance(adj['sharpness'] / 50.0)
                            
                    # Save back to original path (overwriting)
                    img.save(target_image, quality=95)
                    
                return jsonify({'success': True, 'message': 'Image saved successfully'})

            except FileNotFoundError:
                self.logger.error(f"Job folder not found: {job_id}")
                return jsonify({'success': False, 'error': 'Job or image not found'}), 404
                
            except PIL.UnidentifiedImageError:
                self.logger.error(f"Invalid image file for job {job_id}")
                return jsonify({'success': False, 'error': 'Invalid or corrupted image'}), 400
                
            except OSError as e:
                self.logger.exception(f"Failed to save photo for job {job_id}")
                return jsonify({'success': False, 'error': 'Failed to save image'}), 500
                
            except Exception as e:
                self.logger.exception(f"Photo save error for job {job_id}")
                return jsonify({'success': False, 'error': 'Internal server error'}), 500

        @self.app.route('/api/tools/research')
        def price_research():
            """Search eBay sold listings"""
            query = request.args.get('q', '')
            if not query:
                 return jsonify({'stats': {}, 'items': []})
            
            # Use the researcher helper
            results = self.researcher.search_sold(query)
            return jsonify(results)

        # --- Analytics Endpoints ---
        
        @self.app.route('/api/analytics/summary')
        def analytics_summary():
            """Get sales analytics summary"""
            if not self.orders_client:
                return jsonify({'error': 'Analytics module not available'}), 503
            
            days = request.args.get('days', 30, type=int)
            stats = self.orders_client.get_sales_stats(days_back=days)
            return jsonify(stats)
            
        @self.app.route('/api/analytics/orders')
        def analytics_orders():
            """Get raw orders list"""
            if not self.orders_client:
                 return jsonify({'error': 'Analytics module not available'}), 503
                 
            days = request.args.get('days', 90, type=int)
            limit = request.args.get('limit', 50, type=int)
            result = self.orders_client.get_orders(days_back=days, limit=limit)
            return jsonify(result)


        @self.app.route('/api/tools/templates', methods=['GET', 'POST', 'DELETE'])
        def manage_templates():
            """Manage listing templates"""
            if request.method == 'GET':
                return jsonify(self.template_store.get_all())
            
            elif request.method == 'POST':
                data = request.json
                if 'id' in data and any(t['id'] == data['id'] for t in self.template_store.get_all()):
                     updated = self.template_store.update(data['id'], data)
                     return jsonify({'success': True, 'template': updated})
                else:
                    new_template = self.template_store.add(data)
                    return jsonify({'success': True, 'template': new_template})
            
            elif request.method == 'DELETE':
                 template_id = request.args.get('id')
                 if template_id:
                     self.template_store.delete(template_id)
                     return jsonify({'success': True})
                 return jsonify({'success': False, 'error': 'Missing ID'}), 400

        @self.app.route('/api/tools/preview')
        def generate_preview():
            """Generate listing preview HTML"""
            job_id = request.args.get('jobId')
            template_id = request.args.get('templateId')
            
            # Default placeholder data
            title = "Preview Listing"
            desc = "<p>No description available. Please analyze the item first.</p>"
            price = "$99.99"
            photos_count = 0
            template_name = "Default"
            template_fields = {}
            
            # 1. Load Job Data
            if job_id:
                job = self.queue_manager.get_job_by_id(job_id)
                if job:
                   title = job.folder_name
                   folder_path = Path(job.folder_path)
                   
                   # Photos
                   photos_count = len(list(folder_path.glob('*.jpg')) + list(folder_path.glob('*.png')))
                   
                   # Try to read info.txt / ai_data.json
                   info_path = folder_path / "info.txt"
                   if info_path.exists():
                       try: 
                           # Simple text to paragraph conversion
                           raw_desc = info_path.read_text(encoding='utf-8')
                           desc = "".join([f"<p>{line}</p>" for line in raw_desc.split('\n') if line.strip()])
                       except: pass

            # 2. Load Template
            all_tpls = self.template_store.get_all()
            template = None
            
            if template_id:
                template = next((t for t in all_tpls if t['id'] == template_id), None)
            
            # Fallback to default
            if not template and all_tpls:
                 template = next((t for t in all_tpls if t.get('isDefault')), all_tpls[0])
            
            if template:
                template_name = template.get('name', 'Unknown')
                template_fields = template.get('fields', {})

            # 3. Construct HTML
            # This is a basic responsive template that acts as a container
            style_block = """
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; }
                    .container { max-width: 800px; margin: 0 auto; background: #fff; }
                    .header { border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 30px; text-align: center; }
                    .title { font-size: 24px; font-weight: 600; color: #111; margin-bottom: 10px; }
                    .price { font-size: 28px; font-weight: bold; color: #0066cc; }
                    .gallery { background: #f8f8f8; color: #666; height: 300px; display: flex; align-items: center; justify-content: center; border-radius: 8px; margin-bottom: 30px; }
                    .section { margin-bottom: 30px; }
                    .section-title { font-size: 18px; font-weight: 600; border-bottom: 2px solid #0066cc; display: inline-block; margin-bottom: 15px; padding-bottom: 5px; }
                    .specs-table { width: 100%; border-collapse: collapse; }
                    .specs-table td { padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
                    .specs-label { color: #666; width: 40%; }
                    .specs-value { font-weight: 500; }
                    .policy-box { background: #f9f9f9; padding: 15px; border-radius: 8px; display: flex; flex-wrap: wrap; gap: 20px; font-size: 14px; }
                    .policy-item { display: flex; align-items: center; gap: 8px; }
                </style>
            """
            
            specs_rows = ""
            for k, v in template_fields.items():
                specs_rows += f"<tr><td class='specs-label'>{k.title()}</td><td class='specs-value'>{v}</td></tr>"

            html = f"""
                <!DOCTYPE html>
                <html>
                <head>{style_block}</head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1 class="title">{title}</h1>
                            <div class="price">{price}</div>
                        </div>
                        
                        <div class="gallery">
                            {photos_count} Photos Available in Job Folder
                        </div>
                        
                        <div class="section">
                            <div class="section-title">Item Specifics</div>
                            <table class="specs-table">
                                {specs_rows}
                                <tr><td class="specs-label">Template</td><td class="specs-value">{template_name}</td></tr>
                            </table>
                        </div>
                        
                        <div class="section">
                            <div class="section-title">Description</div>
                            {desc}
                        </div>
                        
                        <div class="section">
                            <div class="policy-box">
                                <div class="policy-item"><strong>Shipping:</strong> See Details</div>
                                <div class="policy-item"><strong>Returns:</strong> {template_fields.get('returns', 'See Policy')}</div>
                                <div class="policy-item"><strong>Location:</strong> USA</div>
                            </div>
                        </div>
                    </div>
                </body>
                </html>
            """
            
            # Validation logic (Mock for now, but dynamic based on inputs)
            validation = [
                {'status': 'pass', 'label': 'Title', 'message': f'{len(title)} chars'},
                {'status': 'pass' if photos_count >= 4 else 'warn', 'label': 'Photos', 'message': f'{photos_count} found'},
                {'status': 'pass' if len(desc) > 100 else 'warn', 'label': 'Description', 'message': 'Content length check'},
                {'status': 'pass', 'label': 'Template', 'message': f'Using {template_name}'},
            ]

            return jsonify({
                'html': html,
                'validation': validation
            })

        @self.app.route('/api/policies')
        @self.app.route('/api/policies/<policy_type>')
        def get_policies(policy_type=None):
            """Get eBay business policies (fulfillment, payment, return, locations)"""
            if not HAS_POLICIES:
                return jsonify({'error': 'Policies module not available'}), 500
            
            try:
                if policy_type == 'fulfillment':
                    return jsonify({
                        'policies': ebay_policies.get_fulfillment_policies(),
                        'default': ebay_policies.get_current_defaults().get('fulfillment')
                    })
                elif policy_type == 'payment':
                    return jsonify({
                        'policies': ebay_policies.get_payment_policies(),
                        'default': ebay_policies.get_current_defaults().get('payment')
                    })
                elif policy_type == 'return':
                    return jsonify({
                        'policies': ebay_policies.get_return_policies(),
                        'default': ebay_policies.get_current_defaults().get('return')
                    })
                elif policy_type == 'locations':
                    return jsonify({
                        'locations': ebay_policies.get_inventory_locations(),
                        'default': ebay_policies.get_current_defaults().get('location')
                    })
                else:
                    # Return all policies
                    all_policies = ebay_policies.get_all_policies()
                    defaults = ebay_policies.get_current_defaults()
                    return jsonify({
                        'fulfillment': all_policies['fulfillment'],
                        'payment': all_policies['payment'],
                        'return': all_policies['return'],
                        'locations': all_policies['locations'],
                        'defaults': defaults
                    })
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/listing/create', methods=['POST'])
        def create_listing():
            """Create an eBay listing from a job folder with custom policies"""
            try:
                from create_from_folder import create_listing_from_folder
                
                data = request.json or {}
                job_id = data.get('jobId')
                price = data.get('price', '29.99')
                condition = data.get('condition', 'USED_EXCELLENT')
                fulfillment_policy = data.get('fulfillmentPolicy')
                payment_policy = data.get('paymentPolicy')
                return_policy = data.get('returnPolicy')
                
                # Get job folder path
                if not job_id:
                    return jsonify({'success': False, 'error': 'Missing jobId'}), 400
                
                job = self.queue_manager.get_job_by_id(job_id)
                if not job:
                    return jsonify({'success': False, 'error': 'Job not found'}), 404
                
                folder_path = job.folder_path
                
                # Create listing with optional policy overrides
                result = create_listing_from_folder(
                    folder_path,
                    price=price,
                    condition=condition,
                    fulfillment_policy=fulfillment_policy,
                    payment_policy=payment_policy,
                    return_policy=return_policy
                )
                
                if result:
                    return jsonify({
                        'success': True,
                        'listingId': result if result.startswith('2') else None,
                        'offerId': result if not result.startswith('2') else None,
                        'message': f'Listing created: {result}'
                    })
                else:
                    return jsonify({'success': False, 'error': 'Listing creation failed'}), 500
                    
            except Exception as e:
                self.logger.exception("Listing creation failed")
                return jsonify({'success': False, 'error': 'Internal server error'}), 500

        @self.app.route('/api/listing/create-from-photos', methods=['POST'])
        def create_listing_from_photos():
            """Create eBay listing from uploaded photos (mobile-friendly)"""
            try:
                import uuid
                import shutil
                from datetime import datetime
                
                # Get uploaded files
                uploaded_files = []
                for key in request.files:
                    if key.startswith('photo'):
                        uploaded_files.append(request.files[key])
                
                if not uploaded_files:
                    return jsonify({'success': False, 'error': 'No photos uploaded'}), 400
                
                # Get optional metadata
                item_name = request.form.get('itemName', '').strip()
                price = request.form.get('price', '').strip()
                description = request.form.get('description', '').strip()
                
                # Create temporary job folder
                job_id = f"mobile_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
                job_folder = Path(self.base_path) / 'inbox' / job_id
                job_folder.mkdir(parents=True, exist_ok=True)
                
                self.logger.info(f"Creating listing from {len(uploaded_files)} uploaded photos", 
                                extra={'job_id': job_id})
                
                # Save uploaded photos to job folder
                for i, file in enumerate(uploaded_files):
                    if file and file.filename:
                        # Sanitize filename
                        ext = Path(file.filename).suffix.lower()
                        if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                            ext = '.jpg'
                        
                        photo_path = job_folder / f"photo_{i+1:02d}{ext}"
                        file.save(str(photo_path))
                        self.logger.debug(f"Saved photo: {photo_path.name}")
                
                # Create metadata file if user provided info
                if item_name or price or description:
                    metadata = {}
                    if item_name:
                        metadata['title_hint'] = item_name
                    if price:
                        try:
                            metadata['price'] = float(price)
                        except ValueError:
                            pass
                    if description:
                        metadata['description_hint'] = description
                    
                    metadata_file = job_folder / 'metadata.json'
                    with open(metadata_file, 'w') as f:
                        json.dump(metadata, f, indent=2)
                
                # Process the listing using existing pipeline
                from create_from_folder import create_listing_from_folder
                
                result = create_listing_from_folder(
                    str(job_folder),
                    price=float(price) if price else None
                )
                
                if result:
                    self.logger.info(f"Listing created successfully from mobile upload", 
                                   extra={'job_id': job_id, 'result': result})
                    
                    return jsonify({
                        'success': True,
                        'listingId': result if isinstance(result, str) and result.startswith('2') else None,
                        'offerId': result if isinstance(result, str) and not result.startswith('2') else None,
                        'jobId': job_id,
                        'photosProcessed': len(uploaded_files)
                    })
                else:
                    # Clean up folder on failure
                    if job_folder.exists():
                        shutil.rmtree(job_folder)
                    
                    return jsonify({
                        'success': False,
                        'error': 'Failed to create listing'
                    }), 500
                    
            except FileNotFoundError as e:
                self.logger.error(f"File not found during photo upload: {e}")
                return jsonify({'success': False, 'error': 'Upload processing failed'}), 500
                
            except ImportError as e:
                self.logger.error(f"create_from_folder module not available: {e}")
                return jsonify({'success': False, 'error': 'Listing creation not configured'}), 500
                
            except Exception as e:
                self.logger.exception("Error creating listing from photos")
                return jsonify({'success': False, 'error': 'Internal server error'}), 500

        
        @self.app.route('/api/status')
        def get_status():
            """Get current queue status"""
            stats = self.queue_manager.get_stats()
            
            # Determine overall status
            if self.queue_manager.is_paused():
                status = 'paused'
            elif self.queue_manager.is_processing():
                status = 'processing'
            elif stats['pending'] > 0:
                status = 'ready'
            else:
                status = 'idle'
            
            # Get current job if processing
            current_job = None
            for job in self.queue_manager.jobs:
                if job.status.value == 'processing':
                    current_job = {
                        'name': job.folder_name,
                        'started': job.started_at.isoformat() if job.started_at else None
                    }
                    break
            
            return jsonify({
                'status': status,
                'stats': stats,
                'current_job': current_job,
                'progress': {
                    'current': stats['completed'] + stats['failed'],
                    'total': stats['total'],
                    'percent': int((stats['completed'] + stats['failed']) / max(stats['total'], 1) * 100)
                }
            })
        
        @self.app.route('/api/jobs')
        def get_jobs():
            """Get all jobs with details"""
            jobs = []
            for job in self.queue_manager.jobs:
                jobs.append({
                    'id': job.id,
                    'name': job.folder_name,
                    'status': job.status.value,
                    'listing_id': job.listing_id,
                    'offer_id': job.offer_id,
                    'price': None,  # TODO: Store price in QueueJob
                    'error_type': job.error_type,
                    'error_message': job.error_message,
                    'started_at': job.started_at,
                    'completed_at': job.completed_at,
                })
            return jsonify(jobs)
        
        @self.app.route('/api/stats')
        def get_stats():
            """Get queue statistics"""
            return jsonify(self.queue_manager.get_stats())
        
        @self.app.route('/api/start', methods=['POST'])
        def start_queue():
            """Start queue processing"""
            try:
                self.queue_manager.start_processing()
                return jsonify({'success': True, 'message': 'Queue started'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/pause', methods=['POST'])
        def pause_queue():
            """Pause queue processing"""
            try:
                self.queue_manager.pause()
                return jsonify({'success': True, 'message': 'Queue paused'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/resume', methods=['POST'])
        def resume_queue():
            """Resume queue processing"""
            try:
                self.queue_manager.resume()
                return jsonify({'success': True, 'message': 'Queue resumed'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/retry', methods=['POST'])
        def retry_failed():
            """Retry all failed jobs"""
            try:
                count = len(self.queue_manager.get_failed_jobs())
                self.queue_manager.retry_failed()
                return jsonify({'success': True, 'retried': count})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/clear', methods=['POST'])
        def clear_completed():
            """Clear completed jobs"""
            try:
                self.queue_manager.clear_completed()
                return jsonify({'success': True, 'message': 'Cleared completed jobs'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/upload', methods=['POST'])
        def upload_photos():
            """Upload photos to create a new job"""
            import uuid
            from werkzeug.utils import secure_filename
            
            if 'files[]' not in request.files:
                return jsonify({'success': False, 'error': 'No files uploaded'}), 400
            
            files = request.files.getlist('files[]')
            if not files or files[0].filename == '':
                return jsonify({'success': False, 'error': 'No files selected'}), 400
            
            # Create a unique folder in inbox
            inbox_path = Path(__file__).parent / 'inbox'
            inbox_path.mkdir(exist_ok=True)
            
            # Generate folder name from first file or use timestamp
            job_name = request.form.get('name', '') or f"upload_{uuid.uuid4().hex[:6]}"
            job_name = secure_filename(job_name)
            job_folder = inbox_path / job_name
            job_folder.mkdir(exist_ok=True)
            
            # Save all uploaded files
            saved_count = 0
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    # Check if it's an image
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                        file.save(str(job_folder / filename))
                        saved_count += 1
            
            if saved_count == 0:
                return jsonify({'success': False, 'error': 'No valid image files uploaded'}), 400
            
            # Add to queue
            job = self.queue_manager.add_folder(str(job_folder))
            
            return jsonify({
                'success': True,
                'jobId': job.id,
                'jobName': job.folder_name,
                'imageCount': saved_count,
                'message': f'Created job with {saved_count} images'
            })
        
        @self.app.route('/qr')
        def get_qr_code():
            """Generate QR code for the web URL"""
            if not HAS_QRCODE:
                return "QR code library not installed", 404
            
            url = self.get_url()
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save to bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            return send_file(img_bytes, mimetype='image/png')
    
    def get_local_ip(self):
        """Get the local IP address"""
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def get_url(self):
        """Get the full URL for accessing the web interface"""
        ip = self.get_local_ip()
        return f"http://{ip}:{self.port}"
    
    def start(self):
        """Start the web server in a separate thread"""
        if self._running:
            return
            
        self._running = True

        # Get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "127.0.0.1"

        url = f"http://{local_ip}:{self.port}/app"
        
        print("\n" + "="*50)
        print("📱 MOBILE ACCESS")
        print("="*50)
        print(f"To control from your phone, open:")
        print(f"👉 {url}")
        print("-"*50)
        
        if HAS_QRCODE:
            try:
                qr = qrcode.QRCode(border=1)
                qr.add_data(url)
                qr.make(fit=True)
                qr.print_ascii(invert=True)
                print("(Scan with camera app)")
            except Exception as e:
                print(f"QR Gen failed: {e}")
        print("="*50 + "\n")
        
        self._thread = threading.Thread(
            target=self.app.run,
            kwargs={
                'host': self.host, 
                'port': self.port, 
                'debug': False, 
                'use_reloader': False,
                'threaded': True
            },
            daemon=True
        )
        try:
            self._thread.start()
        except Exception as e:
            print(f"Web server error: {e}")
            self._running = False
    
    def stop(self):
        """Stop the web server"""
        self._running = False
        # Flask doesn't have a clean shutdown in threads, but daemon=True
        # means it will stop when the main app exits
    
    def is_running(self):
        """Check if server is running"""
        return self._running


# Test the server standalone
if __name__ == "__main__":
    from queue_manager import QueueManager
    
    # Use real queue manager for testing tools
    qm = QueueManager()
    qm.clear_all()
    
    # Add our test job
    test_job_path = Path("inbox/test_job_1").absolute()
    if test_job_path.exists():
        job = qm.add_folder(str(test_job_path))
        print(f"Added test job: {job.folder_name} (ID: {job.id})")
    
    server = WebControlServer(qm)
    server.start()
    
    # Keep main thread alive
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
