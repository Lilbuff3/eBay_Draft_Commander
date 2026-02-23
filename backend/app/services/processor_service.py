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
from backend.app.services.queue_manager import NeedsReviewException
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
        
    def _determine_condition(self, folder_path: Path, metadata_condition: str, user_condition: str, log_callback=None) -> str:
        """Determine item condition with explicit priority"""
        def _log(msg, level='info'):
            if log_callback: log_callback(msg, level)
            logger.debug(msg)
        
        if user_condition:
            _log(f"Condition: User Override → {user_condition}")
            return user_condition
        
        if metadata_condition:
            _log(f"Condition: Queue Metadata → {metadata_condition}")
            return metadata_condition
        
        parent_name = folder_path.parent.name
        if parent_name in CONDITION_MAP:
            condition = CONDITION_MAP[parent_name]
            _log(f"⚡ Condition: Folder Name '{parent_name}' → {condition}")
            return condition
        
        _log(f"Condition: Default → {DEFAULT_CONDITION}")
        return DEFAULT_CONDITION

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

        # 1. Condition
        condition = self._determine_condition(folder_path, job_obj.job_metadata.get('condition') if job_obj.job_metadata else None, job_obj.user_condition, log_callback)
        
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

        # 4. Taxonomy & Specifics
        _log("📚 Mapping category taxonomy...")
        cat_result = self.category_mapper.get_category(analysis['title'], analysis['raw_description'])
        self._validate_mandatory_specifics(cat_result.get('name', 'Unknown'), analysis['item_specifics'])

        # 5. Final Pricing
        pricing_result = self.ai_agent.get_final_pricing(analysis['title'], condition, analysis['ai_suggested_price'], job_obj.user_price, log_callback)
        result["timing"]["pricing"] = pricing_result["timing"]

        # 6. Image Upload
        upload = self.image_processor.upload_images(folder_path, log_callback=log_callback)
        if "error" in upload:
            return {"success": False, "error_message": f"Image upload failed: {upload['error']}"}
        result["timing"]["image_upload"] = upload["timing"]

        # 7. Rendering
        template = self._render_listing_template(analysis['title'], analysis['raw_description'], upload["urls"], analysis['item_specifics'], condition)
        result["timing"]["templating"] = template["timing"]

        # 8. Listing Creation
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
            "price": pricing_result["price"], "timing": {**result["timing"], "api": bundle["timing"], "total": time.time() - start_time}
        })
        _log(f"🚀 Listing Created: {result['status']}", level='success')
        return result
