"""
Listing Processor Service
Consolidates logic for creating eBay listings from folder items.
Now integrated with InventoryService (Phase 2) and TemplateManager (Phase 4).
"""
import uuid
import time
from pathlib import Path
from flask import current_app
from backend.app.core.logger import get_logger
from backend.app.services.ai_analyzer import AIAnalyzer
from backend.app.services.pricing_engine import PricingEngine
from backend.app.services.ebay.media import upload_folder
from backend.app.services.ebay_service import eBayService
from backend.app.services.template_manager import get_template_manager

logger = get_logger('processor_service')

class ProcessorService:
    def __init__(self):
        self.pricing_engine = PricingEngine()
        self.ai_analyzer = AIAnalyzer()
        self.ebay_service = eBayService()
        self.template_manager = get_template_manager()
        
    def create_listing(self, folder_path, price="29.99", condition="USED_EXCELLENT"):
        """
        Create listing with Smart Analysis (Research + Category Mapping)
        """
        result = {
            "success": False,
            "listing_id": None,
            "offer_id": None,
            "price": None,
            "status": "error",
            "error_type": None,
            "error_message": None,
            "timing": {}
        }
        
        start_time = time.time()
        folder_path = Path(folder_path)
        
        if not folder_path.exists():
            result["error_type"] = "FolderNotFound"
            result["error_message"] = f"Folder not found: {folder_path}"
            return result

        # Images
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        images = [f for f in folder_path.iterdir() if f.suffix.lower() in image_extensions]
        
        if not images:
            result["error_type"] = "NoImages"
            result["error_message"] = "No images found in folder"
            return result
        
        images.sort(key=lambda x: x.name)
        
        # --- AI Analysis (Enhanced) ---
        ai_start = time.time()
        try:
            # Use Enhanced Mode (Research + Mapping)
            ai_data = self.ai_analyzer.analyze_with_research([str(img) for img in images])
            
            # Map basic fields
            listing_data = ai_data.get('listing', {})
            title = listing_data.get('suggested_title', folder_path.name)
            raw_description = listing_data.get('description', f'Item from {folder_path.name}')
            
            # Map Item Specifics (Pre-mapped by Analyzer)
            item_specifics = ai_data.get('item_specifics', {})
            if not item_specifics and 'identification' in ai_data:
                 item_specifics = ai_data['identification']
                 
            # Extract suggested price
            ai_suggested_price = listing_data.get('suggested_price')
            
            result["timing"]["ai_analysis"] = time.time() - ai_start
            result["timing"]["ai_analysis"] = time.time() - ai_start
        except Exception as e:
            logger.error(f"AI Analysis failed: {e}")
            # STRICT MODE: Do not fall back to folder name.
            # If AI fails, the item cannot be listed according to user rules.
            result["error_type"] = "AI_Analysis_Failed"
            result["error_message"] = f"Strict Mode: AI Analysis failed. {str(e)}"
            return result

        # --- Category Lookup ---
        cat_start = time.time()
        category_id = "30093" # Fallback (Test/Other)
        try:
            from backend.app.services.ebay.taxonomy import get_suggested_category
            cat_suggestion = get_suggested_category(title)
            if cat_suggestion:
                category_id = cat_suggestion['id']
                logger.info(f"Using Category: {cat_suggestion['name']} ({category_id})")
        except Exception as e:
            logger.error(f"Category lookup error: {e}")
        result["timing"]["taxonomy"] = time.time() - cat_start

        # --- Pricing ---
        pricing_start = time.time()
        try:
            price_result = self.pricing_engine.get_price_with_comps(
                title, 
                condition=condition, 
                ai_suggested_price=ai_suggested_price
            )
            final_price = str(price_result['suggested_price']) if price_result['suggested_price'] else None
            
            if not final_price:
                 raise Exception("No valid price found")
                 
            result["timing"]["pricing"] = time.time() - pricing_start
        except Exception as e:
            # STRICT MODE: If pricing fails, we fail.
            logger.error(f"Pricing Logic Failed: {e}")
            result["error_type"] = "Pricing_Failed"
            result["error_message"] = f"Strict Mode: Pricing failed. {str(e)}"
            return result

        # --- Image Upload ---
        upload_start = time.time()
        try:
            image_urls = upload_folder(folder_path, max_images=12)
            if not image_urls:
                image_urls = ["https://placehold.co/800x600.png?text=Placeholder+Image"]
            result["timing"]["image_upload"] = time.time() - upload_start
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            image_urls = ["https://placehold.co/800x600.png?text=Placeholder+Image"]
            result["timing"]["image_upload"] = time.time() - upload_start

        # --- HTML Generation (Phase 4) ---
        html_start = time.time()
        try:
            html_description = self.template_manager.render_description(
                title=title,
                description=raw_description, # AI already returns structured HTML sections in 'description'
                images=image_urls,
                aspects=item_specifics,
                condition=condition
            )
            result["timing"]["templating"] = time.time() - html_start
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            html_description = f"<p>{raw_description}</p>"
            result["timing"]["templating"] = time.time() - html_start

        # --- Inventory API (Phase 2) ---
        api_start = time.time()
        sku = 'DC-' + uuid.uuid4().hex[:8].upper()
        
        try:
            # 1. Create Inventory Item
            item_data = {
                "sku": sku,
                "product": {
                    "title": title[:80],
                    "description": f"Product: {title} - {condition}", 
                    "aspects": item_specifics,
                    "imageUrls": image_urls
                },
                "condition": condition,
                "availability": {
                    "shipToLocationAvailability": {
                        "quantity": 1
                    }
                }
            }
            
            resp, code = self.ebay_service.inventory_service.create_inventory_item(sku, item_data)
            if code not in [200, 204]:
                raise Exception(f"Inventory Item failed ({code}): {resp}")
                
            # 2. Create Offer
            shipping_id = current_app.config.get('EBAY_FULFILLMENT_POLICY')
            payment_id = current_app.config.get('EBAY_PAYMENT_POLICY')
            return_id = current_app.config.get('EBAY_RETURN_POLICY')
            location_key = current_app.config.get('EBAY_MERCHANT_LOCATION', 'default')
            
            offer_payload = {
                'sku': sku,
                'marketplaceId': 'EBAY_US',
                'format': 'FIXED_PRICE',
                'availableQuantity': 1,
                'categoryId': category_id,
                'listingDescription': html_description, 
                'listingPolicies': {
                    'fulfillmentPolicyId': shipping_id,
                    'paymentPolicyId': payment_id,
                    'returnPolicyId': return_id
                },
                'pricingSummary': {'price': {'value': str(final_price), 'currency': 'USD'}},
                'merchantLocationKey': location_key
            }
            
            resp, code = self.ebay_service.inventory_service.create_offer(offer_payload)
            if code not in [200, 201]:
                 raise Exception(f"Offer Creation failed ({code}): {resp}")
            
            offer_id = resp.get('offerId')
            result["offer_id"] = offer_id
            
            # --- Auto-Publish (Phase 5+) ---
            if current_app.config.get('AUTO_PUBLISH'):
                logger.info(f"Auto-Publishing Offer: {offer_id}")
                pub_resp, pub_code = self.ebay_service.publish_listing(offer_id)
                if pub_code == 200:
                    result["listing_id"] = pub_resp.get('listingId')
                    result["status"] = "active"
                    result["success"] = True
                    logger.info(f"Published successfully! Listing ID: {result['listing_id']}")
                else:
                    logger.warning(f"Auto-Publish failed: {pub_resp}")
                    result["status"] = "draft (publish_failed)"
                    result["success"] = True # Still created the draft
            else:
                result["status"] = "draft"
                result["success"] = True
            
            result["timing"]["api"] = time.time() - api_start
            
        except Exception as e:
             result["error_type"] = "APIError"
             result["error_message"] = str(e)
             result["timing"]["api"] = time.time() - api_start
             return result

        result["timing"]["total"] = time.time() - start_time
        result["price"] = final_price
        
        return result
