"""
Listing Processor Service
Consolidates logic for creating eBay listings from folder items.
Now integrated with InventoryService (Phase 2) and TemplateManager (Phase 4).
"""
import json
import uuid
import time
import asyncio
from pathlib import Path
from flask import current_app
from backend.app.core.logger import get_logger
from backend.app.services.ai_analyzer import AIAnalyzer
from backend.app.services.pricing_engine import PricingEngine
from backend.app.core.validator import validate_price, validate_title, validate_condition, ValidationError
from backend.app.services.ebay.media import upload_folder
from backend.app.services.ebay_service import eBayService
from backend.app.services.template_manager import get_template_manager
from backend.app.core.constants import (
    CONDITION_MAP,
    DEFAULT_CATEGORY_ID,
    DEFAULT_CONDITION,
    MAX_IMAGES_PER_LISTING,
    TITLE_MAX_LENGTH,
    ASPECT_VALUE_MAX_LENGTH,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MIN_PRICE
)

from backend.app.services.category_mapper import CategoryMapper

logger = get_logger('processor_service')

class ProcessorService:
    def __init__(self):
        self.pricing_engine = PricingEngine()
        self.ai_analyzer = AIAnalyzer()
        self.ebay_service = eBayService()
        self.template_manager = get_template_manager()
        self.category_mapper = CategoryMapper()
        
    def _determine_condition(self, folder_path: Path, metadata_condition: str, user_condition: str, log_callback=None) -> str:
        """
        Determine item condition with explicit priority:
        1. User override (DB) - HIGHEST
        2. Queue metadata
        3. Parent folder name
        4. Default
        
        Args:
            folder_path: Path to item folder
            metadata_condition: Condition from queue metadata
            user_condition: User override condition from job object
            log_callback: Optional logging callback
        
        Returns:
            eBay condition code (e.g., 'USED_EXCELLENT')
        """
        def _log(msg, level='info'):
            if log_callback: log_callback(msg, level)
            logger.debug(msg)
        
        # Priority 1: User Override
        if user_condition:
            _log(f"Condition: User Override → {user_condition}")
            return user_condition
        
        # Priority 2: Queue Metadata
        if metadata_condition:
            _log(f"Condition: Queue Metadata → {metadata_condition}")
            return metadata_condition
        
        # Priority 3: Folder Name
        parent_name = folder_path.parent.name
        if parent_name in CONDITION_MAP:
            condition = CONDITION_MAP[parent_name]
            _log(f"⚡ Condition: Folder Name '{parent_name}' → {condition}")
            return condition
        
        # Priority 4: Default
        _log(f"Condition: Default → {DEFAULT_CONDITION}")
        return DEFAULT_CONDITION

    def _perform_enhanced_ai_analysis(self, folder_path: Path, images: list, condition: str, job_obj: object, log_callback: callable = None) -> dict:
        """Perform AI analysis or use cached data from DB object"""
        def _log(msg, level="info"):
            if log_callback: log_callback(msg, level)
            getattr(logger, level)(msg)

        try:
            # Check DB object for cached AI data
            if job_obj.ai_data and job_obj.ai_data.get('listing'):
                _log("Using cached AI analysis from Database")
                ai_data = job_obj.ai_data
            else:
                _log(f"🧠 Analyzing {len(images)} images with Gemini Vision (Research Mode)...")
                ai_data = self.ai_analyzer.analyze_with_research([str(img) for img in images])
                
                if ai_data.get('error'):
                    if ai_data.get('raw'):
                        _log(f"AI Raw Response (Partial): {ai_data['raw'][:200]}...", level='warning')
                    raise Exception(f"AI Analyzer Error: {ai_data['error']}")
                
                # Update the job object with new AI data so it gets saved
                job_obj.ai_data = ai_data

            # --- NOS/Condition Force Logic ---
            if folder_path.parent.name == 'New Old Stock' or condition == 'NEW_OTHER':
                if 'condition' not in ai_data: ai_data['condition'] = {}
                ai_data['condition']['state'] = 'New Old Stock'
                ai_data['condition']['is_nos'] = True

            listing_data = ai_data.get('listing', {})
            if not listing_data:
                raise Exception("AI returned no output with 'listing' key")

            # Title Determination
            if job_obj.user_title:
                title = job_obj.user_title
                logger.info(f"Using User Override Title: {title}")
            else:
                title = listing_data.get('suggested_title')
                if not title:
                    raise Exception("AI did not generate a title")

            # Description Determination
            if job_obj.user_description:
                raw_description = job_obj.user_description
            else:
                raw_description = listing_data.get('description_html') or listing_data.get('description') or f"Item {folder_path.name}"
            
            # Item Specifics mapping
            item_specifics = ai_data.get('item_specifics', {})
            if not item_specifics and 'identification' in ai_data:
                item_specifics = ai_data['identification']
            
            # Allow user overrides for specific aspects if we add that later
            # For now just use what we have

            return {
                "ai_data": ai_data,
                "title": title,
                "raw_description": raw_description,
                "item_specifics": item_specifics,
                "ai_suggested_price": listing_data.get('suggested_price', 0)
            }

        except Exception as e:
            logger.error(f"AI Analysis failed: {e}")
            return {"error": str(e)}

    def _determine_final_pricing(self, title: str, condition: str, ai_suggested_price: float, user_price: str, log_callback: callable = None) -> dict:
        """Determine the final price using research engine and user overrides"""
        def _log(msg, level="info"):
            if log_callback: log_callback(msg, level)
            getattr(logger, level)(msg)

        if user_price:
            final_price = str(user_price)
            _log(f"Using User Override Price: {final_price}")
            return {"price": final_price, "timing": 0}

        pricing_start = time.time()
        try:
            _log("💰 Researching pricing & comps...")
            price_result = self.pricing_engine.get_price_with_comps(
                title, 
                condition=condition, 
                ai_suggested_price=ai_suggested_price
            )
            final_price = str(price_result['suggested_price']) if price_result['suggested_price'] else "0.00"
            _log(f"💵 Suggested Price: ${final_price}")
            return {"price": final_price, "timing": time.time() - pricing_start}
        except Exception as e:
            _log(f"Pricing Logic Failed: {e}", level='error')
            return {
                "price": "0.00", 
                "warning": "Price logic failed. Manual input required.",
                "timing": time.time() - pricing_start
            }

    def _upload_images(self, folder_path: Path, max_images: int = 12, log_callback: callable = None) -> dict:
        """Upload images to eBay Picture Services"""
        def _log(msg, level="info"):
            if log_callback: log_callback(msg, level)
            getattr(logger, level)(msg)

        upload_start = time.time()
        try:
            _log(f"☁️ Uploading images to eBay from {folder_path.name}...")
            image_urls = upload_folder(folder_path, max_images=max_images)
            if not image_urls:
                raise Exception("No images were uploaded successfully")
            return {"urls": image_urls, "timing": time.time() - upload_start}
        except Exception as e:
            _log(f"Image upload failed: {e}", level='error')
            return {"error": str(e), "timing": time.time() - upload_start}

    def _render_listing_template(self, title: str, description: str, images: list, aspects: dict, condition: str) -> dict:
        """Render the listing HTML using the template manager"""
        timing_start = time.time()
        try:
            html = self.template_manager.render_description(
                title=title,
                description=description,
                images=images,
                aspects=aspects,
                condition=condition
            )
            return {"html": html, "timing": time.time() - timing_start}
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return {"html": f"<p>{description}</p>", "timing": time.time() - timing_start}

    def _create_ebay_listing_bundle(self, title: str, final_price: str, condition: str, category_id: str, html_description: str, image_urls: list, item_specifics: dict, shipping_policy: str, ai_data: dict, result_obj: dict) -> dict:
        """Create eBay inventory item and offer via MCP bundle with auto-publish thresholds"""
        timing_start = time.time()
        sku = 'DC-' + uuid.uuid4().hex[:8].upper()
        
        try:
            # 0. Final Input Validation
            title = validate_title(title)
            final_price = str(validate_price(final_price))
            condition = validate_condition(condition)
            
            # 1. Aspect Cleaning
            cleaned_aspects = {}
            for k, v in item_specifics.items():
                if not v: continue
                val = v[0] if isinstance(v, list) else v
                val = str(val)
                if k == 'Brand' and val.upper() == 'OEM': val = 'Unbranded'
                if len(val) > ASPECT_VALUE_MAX_LENGTH:
                    if ',' in val:
                        parts = val.split(',')
                        val = parts[0].strip() if len(parts[0]) <= ASPECT_VALUE_MAX_LENGTH else val[:62] + "..."
                    else:
                        val = val[:62] + "..."
                cleaned_aspects[k] = [val]

            # 2. Build Inventory Item
            item_data = {
                "sku": sku,
                "product": {
                    "title": title[:TITLE_MAX_LENGTH],
                    "description": f"Product: {title} - {condition}", 
                    "aspects": cleaned_aspects,
                    "imageUrls": image_urls
                },
                "condition": condition,
                "availability": {
                    "shipToLocationAvailability": {
                        "quantity": 1,
                        "merchantLocationKey": current_app.config.get('EBAY_MERCHANT_LOCATION', 'DEFAULT')
                    }
                }
            }
            
            # 3. Handle Auto-Publish thresholds
            should_publish = False
            publish_reason = ""
            
            if current_app.config.get('AUTO_PUBLISH'):
                confidence = ai_data.get('identification', {}).get('confidence_score', 0)
                try:
                    confidence = int(confidence)
                except:
                    confidence = 0
                
                conf_thresh = current_app.config.get('CONFIDENCE_THRESHOLD', DEFAULT_CONFIDENCE_THRESHOLD)
                min_price = current_app.config.get('AUTO_PUBLISH_MIN_PRICE', DEFAULT_MIN_PRICE)
                
                price_val = 0.0
                try:
                    price_val = float(final_price)
                except: pass
                
                if confidence >= conf_thresh and price_val >= min_price and not result_obj.get('price_warning'):
                    should_publish = True
                    publish_reason = f"High Confidence ({confidence}%) & Price (${price_val})"
                else:
                    logger.info(f"Skipping Auto-Publish: Conf={confidence}% (Req {conf_thresh}), Price=${price_val} (Req ${min_price}), Warnings={bool(result_obj.get('price_warning'))}")

            # 4. Prepare Offer Payload
            shipping_id = shipping_policy or current_app.config.get('EBAY_FULFILLMENT_POLICY')
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

            # 5. Call eBay Service Bundle
            logger.info(f"Delegating listing bundle creation for SKU {sku} to eBayService...")
            bundle_result = self.ebay_service.create_listing_bundle(
                sku=sku,
                item_data=item_data,
                offer_data=offer_payload,
                auto_publish=should_publish
            )
            
            if not bundle_result.get('success'):
                error_details = "; ".join(bundle_result.get('details', []))
                raise Exception(f"eBay Bundle failed: {error_details}")

            return {
                "success": True,
                "listing_id": bundle_result.get('listing_id'),
                "offer_id": bundle_result.get('offer_id'),
                "status": bundle_result.get('status'),
                "published": bundle_result.get('status') == 'active',
                "publish_reason": publish_reason,
                "timing": time.time() - timing_start
            }

        except Exception as e:
            logger.error(f"eBay Bundle failed: {e}")
            return {"error": str(e), "timing": time.time() - timing_start}

    def create_listing(self, job_obj, log_callback=None):
        """
        Create listing with Smart Analysis (Research + Category Mapping).
        Auto-detects condition from metadata or parent folder name.
        """
        def _log(msg, level='info'):
            if log_callback: log_callback(msg, level)
            logger.info(msg)
        
        folder_path = Path(job_obj.folder_path)
        
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
        
        if not folder_path.exists():
            result["error_type"] = "FolderNotFound"
            result["error_message"] = f"Folder not found: {folder_path}"
            return result

        # --- Condition Logic ---
        condition_meta = job_obj.job_metadata.get('condition') if job_obj.job_metadata else None
        condition = self._determine_condition(folder_path, condition_meta, job_obj.user_condition, log_callback)
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        images = [f for f in folder_path.iterdir() if f.suffix.lower() in image_extensions]
        
        if not images:
            result["error_type"] = "NoImages"
            result["error_message"] = "No images found in folder"
            return result
        
        images.sort(key=lambda x: x.name)
        
        # --- AI Analysis (Enhanced) ---
        ai_start = time.time()
        analysis = self._perform_enhanced_ai_analysis(folder_path, images, condition, job_obj, log_callback)
        
        if "error" in analysis:
            result["error_type"] = "AI_Analysis_Failed"
            result["error_message"] = f"Strict Mode: AI Analysis failed. {analysis['error']}"
            return result
            
        ai_data = analysis["ai_data"]
        title = analysis["title"]
        raw_description = analysis["raw_description"]
        item_specifics = analysis["item_specifics"]
        ai_suggested_price = analysis["ai_suggested_price"]
        
        result["timing"]["ai_analysis"] = time.time() - ai_start
        
        # Update job with AI findings if not already set (though _perform_enhanced_ai_analysis sets ai_data on job_obj)
        # We can also update item specifics if we want to separate them
        job_obj.item_specifics = item_specifics

        # --- Category Lookup ---
        cat_start = time.time()
        category_id = DEFAULT_CATEGORY_ID  # Fallback
        
        try:
            _log("📚 Mapping category taxonomy...")
            cat_result = self.category_mapper.get_category(title, raw_description)
            category_id = cat_result['id']
            if cat_result.get('warning'):
                 result['category_warning'] = cat_result['warning']
            _log(f"✅ Mapped to Category ID: {category_id}")
        except Exception as e:
            _log(f"Category lookup error: {e}", level='error')
            
        result["timing"]["taxonomy"] = time.time() - cat_start

        # --- Pricing ---
        pricing = self._determine_final_pricing(title, condition, ai_suggested_price, job_obj.user_price, log_callback)
        final_price = pricing["price"]
        if "warning" in pricing:
            result["price_warning"] = pricing["warning"]
        result["timing"]["pricing"] = pricing["timing"]

        # --- Image Upload ---
        upload = self._upload_images(folder_path, max_images=12, log_callback=log_callback)
        if "error" in upload:
            result["error_type"] = "ImageUploadFailed"
            result["error_message"] = f"Cannot create listing without images: {upload['error']}"
            result["timing"]["image_upload"] = upload["timing"]
            return result
            
        image_urls = upload["urls"]
        result["timing"]["image_upload"] = upload["timing"]

        # --- HTML Generation (Phase 4) ---
        template = self._render_listing_template(title, raw_description, image_urls, item_specifics, condition)
        html_description = template["html"]
        result["timing"]["templating"] = template["timing"]

        # --- eBay Listing Bundle (Inventory + Offer + Publish) ---
        shipping_policy = None
        if job_obj.job_metadata:
             shipping_policy = job_obj.job_metadata.get('fulfillment_policy')
        
        bundle = self._create_ebay_listing_bundle(
            title=title,
            final_price=final_price,
            condition=condition,
            category_id=category_id,
            html_description=html_description,
            image_urls=image_urls,
            item_specifics=item_specifics,
            shipping_policy=shipping_policy,
            ai_data=ai_data,
            result_obj=result 
        )
        
        if "error" in bundle:
            result["error_type"] = "APIError"
            result["error_message"] = bundle["error"]
            result["timing"]["api"] = bundle["timing"]
            return result
            
        result["offer_id"] = bundle.get('offer_id')
        result["listing_id"] = bundle.get('listing_id')
        result["status"] = bundle.get('status')
        result["success"] = True
        result["timing"]["api"] = bundle["timing"]
        
        if bundle.get('published'):
             _log(f"🚀 Auto-Publish Result: {result['status']} ({bundle.get('publish_reason')})", level='success')

        result["timing"]["total"] = time.time() - start_time
        result["price"] = final_price
        
        return result
