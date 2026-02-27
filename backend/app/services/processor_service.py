"""
Listing Processor Service
Consolidates logic for creating eBay listings from folder items.
Refactored to delegate core tasks to ListingAIAgent and ImageProcessor.
"""
import os
import uuid
import time
from pathlib import Path
from flask import current_app
from backend.app.core.logger import get_logger
from backend.app.core.validator import validate_price, validate_title, validate_condition
from backend.app.services.ebay_service import eBayService
from backend.app.services.template_manager import get_template_manager
from backend.app.services.image_processor import ImageProcessor
from backend.app.services.listing_ai_agent import ListingAIAgent
from backend.app.services.category_mapper import CategoryMapper
from backend.app.core.exceptions import NeedsReviewException
from backend.app.core.constants import (
    CONDITION_MAP,
    CONDITION_ID_MAP,
    DEFAULT_CATEGORY_ID,
    DEFAULT_CONDITION,
    TITLE_MAX_LENGTH,
    ASPECT_VALUE_MAX_LENGTH,
    SUPPORTED_IMAGE_EXTENSIONS
)

logger = get_logger('processor_service')

class ProcessorService:
    def __init__(self):
        self.ebay_service = eBayService()
        self.template_manager = get_template_manager()
        self.category_mapper = CategoryMapper()
        self.image_processor = ImageProcessor(self.ebay_service)
        self.ai_agent = ListingAIAgent()
        
    # Map AI condition states to our internal condition enum values
    AI_CONDITION_MAP = {
        'new': 'NEW',
        'brand new': 'NEW',
        'new open box': 'NEW_OTHER',
        'new other': 'NEW_OTHER',
        'new old stock': 'NEW_OTHER',
        'new with defects': 'NEW_WITH_DEFECTS',
        'used - like new': 'LIKE_NEW',
        'like new': 'LIKE_NEW',
        'used - good': 'USED_GOOD',
        'used - excellent': 'USED_EXCELLENT',
        'used - acceptable': 'USED_ACCEPTABLE',
        'used': 'USED_GOOD',
        'for parts': 'FOR_PARTS_OR_NOT_WORKING',
        'for parts or not working': 'FOR_PARTS_OR_NOT_WORKING',
    }

    def _determine_condition(self, folder_path: Path, metadata_condition: str, user_condition: str, log_callback=None) -> str:
        """Determine item condition with explicit priority"""
        def _log(msg, level='info'):
            if log_callback: log_callback(msg, level)
            logger.debug(msg)

        if user_condition:
            _log(f"Condition: User Override -> {user_condition}")
            return user_condition

        if metadata_condition:
            _log(f"Condition: Queue Metadata -> {metadata_condition}")
            return metadata_condition

        parent_name = folder_path.parent.name
        if parent_name in CONDITION_MAP:
            condition = CONDITION_MAP[parent_name]
            _log(f"Condition: Folder Name '{parent_name}' -> {condition}")
            return condition

        _log(f"Condition: Default -> {DEFAULT_CONDITION}")
        return DEFAULT_CONDITION

    def _refine_condition_from_ai(self, current_condition: str, ai_data: dict, has_user_override: bool, has_metadata: bool, has_folder_match: bool, log_callback=None) -> str:
        """Refine condition using AI-detected state, if no explicit override exists.

        Only upgrades/changes condition when it came from DEFAULT_CONDITION
        (i.e. no user override, no metadata, no folder match).
        """
        def _log(msg, level='info'):
            if log_callback: log_callback(msg, level)
            logger.debug(msg)

        # Don't override explicit user/metadata/folder conditions
        if has_user_override or has_metadata or has_folder_match:
            return current_condition

        condition_data = ai_data.get('condition', {})
        ai_state = condition_data.get('state', '').strip().lower()

        if not ai_state:
            return current_condition

        mapped = self.AI_CONDITION_MAP.get(ai_state)
        if mapped and mapped != current_condition:
            _log(f"Condition: AI detected '{condition_data.get('state')}' -> {mapped}")
            return mapped

        return current_condition

    def _validate_mandatory_specifics(self, category_name: str, specifics: dict):
        """Check if mandatory eBay Item Specifics are present"""
        if not category_name:
            return
            
        cat_lower = category_name.lower()
        missing = []
        
        if 'shoe' in cat_lower or 'sneaker' in cat_lower or 'boot' in cat_lower:
            if 'US Shoe Size' not in specifics and 'US Shoe Size (Men\'s)' not in specifics and 'US Shoe Size (Women\'s)' not in specifics:
                missing.append('US Shoe Size')
            if 'Brand' not in specifics:
                missing.append('Brand')
                
        elif 'clothing' in cat_lower or 'shirt' in cat_lower or 'pant' in cat_lower or 'jacket' in cat_lower:
            if 'Brand' not in specifics:
                missing.append('Brand')
            if 'Size Type' not in specifics:
                specifics['Size Type'] = 'Regular'
            if not any('Size' in k for k in specifics.keys()):
                missing.append('Size')
                
        if missing:
            raise NeedsReviewException(f"Missing mandatory Item Specifics for category '{category_name}': {', '.join(missing)}")

    def _render_listing_template(self, title: str, description: str, images: list, aspects: dict, condition: str) -> dict:
        """Render the listing HTML"""
        timing_start = time.time()
        try:
            html = self.template_manager.render_description(
                title=title, description=description, images=images, aspects=aspects, condition=condition
            )
            return {"html": html, "timing": time.time() - timing_start}
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return {"html": f"<p>{description}</p>", "timing": time.time() - timing_start}

    def _create_trading_api_listing(self, title: str, final_price: str, condition: str, category_id: str, html_description: str, image_urls: list, item_specifics: dict, shipping_policy: str, scheduled_time: str = None) -> dict:
        """Create eBay Listing via Trading API"""
        timing_start = time.time()
        sku = 'DC-' + uuid.uuid4().hex[:8].upper()
        
        try:
            title = validate_title(title[:TITLE_MAX_LENGTH])
            final_price = str(validate_price(final_price))
            condition = validate_condition(condition)
            condition_id = CONDITION_ID_MAP.get(condition, '3000')
            
            cleaned_aspects = {}
            for k, v in item_specifics.items():
                if not v: continue
                val = v[0] if isinstance(v, list) else v
                val = str(val)[:ASPECT_VALUE_MAX_LENGTH]
                if k == 'Brand' and val.upper() == 'OEM': val = 'Unbranded'
                cleaned_aspects[k] = [val]

            item_data = {
                'title': title, 'description': html_description, 'price': final_price,
                'category_id': category_id, 'condition_id': condition_id, 'sku': sku,
                'image_urls': image_urls, 'payment_policy_id': current_app.config.get('EBAY_PAYMENT_POLICY'),
                'return_policy_id': current_app.config.get('EBAY_RETURN_POLICY'),
                'fulfillment_policy_id': shipping_policy or current_app.config.get('EBAY_FULFILLMENT_POLICY'),
                'item_specifics': cleaned_aspects, 'postal_code': current_app.config.get('EBAY_POSTAL_CODE'),
                'item_location': os.environ.get('EBAY_ITEM_LOCATION', 'Clovis, CA')
            }

            api_result = self.ebay_service.create_trading_api_listing(item_data, schedule_time=scheduled_time)
            if not api_result.get('success'):
                raise Exception(f"Trading API Failed: {api_result.get('error')}")

            return {
                "success": True, "listing_id": api_result.get('item_id'),
                "status": api_result.get('status'), "timing": time.time() - timing_start
            }
        except Exception as e:
            logger.error(f"Trading API Creation failed: {e}")
            return {"error": str(e), "timing": time.time() - timing_start}

    def create_listing(self, job_obj, log_callback=None):
        """Main entry point for processing and creating a listing"""
        def _log(msg, level='info'):
            if log_callback: log_callback(msg, level)
            logger.info(msg)
        
        start_time = time.time()
        folder_path = Path(job_obj.folder_path)
        result = {"success": False, "timing": {}}
        
        if not folder_path.exists():
            return {"success": False, "error_message": f"Folder not found: {folder_path}"}

        # 1. Initial Condition (may be refined after AI analysis)
        metadata_condition = job_obj.job_metadata.get('condition') if job_obj.job_metadata else None
        condition = self._determine_condition(folder_path, metadata_condition, job_obj.user_condition, log_callback)
        has_user_override = bool(job_obj.user_condition)
        has_metadata = bool(metadata_condition)
        has_folder_match = folder_path.parent.name in CONDITION_MAP

        # 2. Images
        images = sorted([f for f in folder_path.iterdir() if f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS])
        if not images:
            return {"success": False, "error_message": "No images found"}

        # 3. AI Analysis
        ai_start = time.time()
        analysis = self.ai_agent.analyze_item(job_obj, [str(img) for img in images], condition, log_callback)
        result["timing"]["ai_analysis"] = time.time() - ai_start
        if not analysis.get('success'):
             return {"success": False, "error_message": analysis.get('error')}

        # Capture confidence score
        confidence_score = analysis.get('confidence_score', 0.0)
        job_obj.confidence_score = confidence_score

        # 3b. Refine condition using AI detection (only if no explicit override)
        condition = self._refine_condition_from_ai(
            condition, analysis.get('ai_data', {}),
            has_user_override, has_metadata, has_folder_match, log_callback
        )

        # 4. Taxonomy & Specifics
        _log("Mapping category taxonomy...")
        # Use AI-provided category if available
        ai_category_id = analysis.get('category_id')
        
        if ai_category_id:
            # If we have an AI-selected ID, we still want to get the name for validation/logging
            # We can mock a cat_result or update category_mapper to handle IDs
            cat_result = {
                'id': ai_category_id,
                'name': analysis.get('item_specifics', {}).get('category_name', 'AI Selected'),
                'source': 'ai_selection'
            }
        else:
            # Fallback to legacy mapper if AI didn't provide one (though mapper now returns None too)
            cat_result = self.category_mapper.get_category(analysis['title'], analysis['raw_description'])
        
        self._validate_mandatory_specifics(cat_result.get('name', 'Unknown'), analysis['item_specifics'])

        # 5. Final Pricing
        shipping_cost = analysis.get('shipping_cost')
        pricing_result = self.ai_agent.get_final_pricing(
            analysis['title'], 
            condition, 
            analysis['ai_suggested_price'], 
            job_obj.user_price, 
            shipping_cost=shipping_cost,
            log_callback=log_callback
        )
        result["timing"]["pricing"] = pricing_result["timing"]

        # 6. Image Upload
        upload = self.image_processor.upload_images(folder_path, log_callback=log_callback)
        if "error" in upload:
            return {"success": False, "error_message": f"Image upload failed: {upload['error']}"}
        result["timing"]["image_upload"] = upload["timing"]

        # 7. Rendering
        template = self._render_listing_template(analysis['title'], analysis['raw_description'], upload["urls"], analysis['item_specifics'], condition)
        result["timing"]["templating"] = template["timing"]

        # 8. Hybrid Publishing Logic (Phase 2 Intercept)
        auto_publish = str(os.environ.get('AUTO_PUBLISH', 'false')).lower() == 'true'
        threshold = float(os.environ.get('CONFIDENCE_THRESHOLD', 0.85))
        
        # CATEGORY GUARD: Force review if category is missing
        missing_category = not cat_result.get('id')
        
        if not auto_publish or confidence_score < threshold or missing_category:
            if missing_category:
                reason = "Missing Category (AI could not determine accurate eBay category)"
            elif not auto_publish:
                reason = "AUTO_PUBLISH=false"
            else:
                reason = f"Low Confidence ({confidence_score:.2f} < {threshold})"
            
            _log(f"Routing to Review Queue: {reason}", level='warning')
            
            result.update({
                "success": True,
                "status": "pending_review",
                "price": pricing_result["price"],
                "title": analysis['title'],
                "condition": condition,
                "confidence_score": confidence_score,
                "timing": {**result["timing"], "total": time.time() - start_time}
            })
            return result

        # 9. Listing Creation (Proceed if High Confidence & Auto-Publish)
        bundle = self._create_trading_api_listing(
            title=analysis['title'], final_price=pricing_result["price"], condition=condition,
            category_id=cat_result['id'], html_description=template["html"],
            image_urls=upload["urls"], item_specifics=analysis['item_specifics'],
            shipping_policy=job_obj.job_metadata.get('fulfillment_policy') if job_obj.job_metadata else None,
            scheduled_time=job_obj.scheduled_time
        )
        
        if "error" in bundle:
            return {"success": False, "error_message": bundle["error"]}
            
        result.update({
            "success": True, "listing_id": bundle['listing_id'], "status": bundle['status'],
            "price": pricing_result["price"], "title": analysis['title'],
            "condition": condition,
            "timing": {**result["timing"], "api": bundle["timing"], "total": time.time() - start_time}
        })
        _log(f"Listing Created: {result['status']}", level='success')
        return result
