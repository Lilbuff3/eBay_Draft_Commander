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
from backend.app.core.results_logger import log_listing_result
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

    def _validate_and_enrich_specifics(self, category_id: str, specifics: dict, _log=None) -> list:
        """
        Fetch eBay's required/recommended aspects for the category,
        auto-fill single-value required aspects, perform fuzzy matching,
        and return the full aspect schema for the frontend.
        """
        if not category_id:
            return []

        from backend.app.services.ebay.taxonomy import get_item_aspects
        aspects = get_item_aspects(category_id)
        
        required_aspects = aspects.get('required', [])
        optional_aspects = aspects.get('optional', [])

        for aspect in required_aspects:
            aspect['isRequired'] = True
            if 'values' in aspect:
                aspect['values'] = aspect['values'][:50] # Cap to avoid huge payloads

        for aspect in optional_aspects:
            aspect['isRequired'] = False
            if 'values' in aspect:
                aspect['values'] = aspect['values'][:50]

        full_schema = required_aspects + optional_aspects

        if not full_schema:
            return []

        for aspect in required_aspects:
            name = aspect.get('name')
            if not name:
                continue

            # Auto-fill if there's exactly one allowed value and missing
            if (name not in specifics or not specifics[name]) and aspect.get('values') and len(aspect['values']) == 1:
                specifics[name] = aspect['values'][0]
                if _log:
                    _log(f"Auto-filled required aspect: {name} = {aspect['values'][0]}")

        # Fuzzy match existing values against the schema
        for name, value in list(specifics.items()):
            if not isinstance(value, str):
                continue
            schema_aspect = next((a for a in full_schema if a.get('name') == name), None)
            if schema_aspect and schema_aspect.get('values'):
                allowed_values = schema_aspect['values']
                if value in allowed_values:
                    continue
                # Fuzzy logic
                value_lower = value.lower()
                for allowed in allowed_values:
                    allowed_lower = allowed.lower()
                    if value_lower == allowed_lower or value_lower in allowed_lower:
                        specifics[name] = allowed
                        if _log:
                            _log(f"Fuzzy matched aspect: {name} = '{value}' -> '{allowed}'")
                        break

        return full_schema

    def _render_listing_template(self, title: str, description: str, images: list,
                                  aspects: dict, condition: str, research: dict = None) -> dict:
        """Render the listing HTML, enriched with web research data if available."""
        timing_start = time.time()
        try:
            html = self.template_manager.render_description(
                title=title, description=description, images=images, aspects=aspects, condition=condition
            )

            # Append research-sourced sections (inline styles only — eBay strips <style> on mobile)
            if research:
                from html import escape as html_escape
                research_sections = []

                # Compatible systems / devices
                compatible = research.get('compatible_with', [])
                if compatible:
                    compat_items = ''.join(
                        f'<li style="padding:4px 0;">{html_escape(str(c))}</li>' for c in compatible[:8]
                    )
                    research_sections.append(
                        '<div style="margin:15px 0; padding:12px; background:#f8f9fa; border-radius:5px;">'
                        '<h3 style="margin:0 0 8px 0;">Compatible With</h3>'
                        f'<ul style="margin:0; padding-left:20px;">{compat_items}</ul>'
                        '</div>'
                    )

                # Research notes (contextual details from web research)
                notes = research.get('notes', '')
                if notes and len(notes) > 10:
                    research_sections.append(
                        f'<p style="margin:10px 0; font-style:italic; color:#555;">{html_escape(str(notes))}</p>'
                    )

                if research_sections:
                    html += '\n'.join(research_sections)

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

            # Validate condition ID against category's allowed conditions
            from backend.app.services.ebay.taxonomy import validate_condition_for_category
            validated_id = validate_condition_for_category(condition_id, category_id)
            if validated_id != condition_id:
                logger.warning(f"Condition ID adjusted: {condition_id} -> {validated_id} for category {category_id}")
                condition_id = validated_id

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
            return {"success": False, "error_type": "folder_not_found", "error_message": f"Folder not found: {folder_path}"}

        # 1. Initial Condition (may be refined after AI analysis)
        metadata_condition = job_obj.job_metadata.get('condition') if job_obj.job_metadata else None
        condition = self._determine_condition(folder_path, metadata_condition, job_obj.user_condition, log_callback)
        has_user_override = bool(job_obj.user_condition)
        has_metadata = bool(metadata_condition)
        has_folder_match = folder_path.parent.name in CONDITION_MAP

        # 2. Images
        images = sorted([f for f in folder_path.iterdir() if f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS])
        if not images:
            return {"success": False, "error_type": "no_images", "error_message": "No images found"}

        # 3. AI Analysis
        ai_start = time.time()
        analysis = self.ai_agent.analyze_item(job_obj, [str(img) for img in images], condition, log_callback)
        result["timing"]["ai_analysis"] = time.time() - ai_start
        if not analysis.get('success'):
             return {"success": False, "error_type": "ai_analysis_failed", "error_message": analysis.get('error')}

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

        # 4a. Check correction cache first (human feedback loop)
        from backend.app.services.category_correction_cache import get_correction_cache
        correction = get_correction_cache().lookup(analysis['title'])

        # Use AI-provided category if available
        ai_category_id = analysis.get('category_id')

        if correction:
            cat_result = correction
            _log(f"Category from correction cache: {correction['name']} ({correction['id']})")
        elif ai_category_id:
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
        
        # 4b. Fetch eBay required aspects and validate/enrich item specifics
        ebay_aspect_schema = self._validate_and_enrich_specifics(
            cat_result.get('id'), analysis['item_specifics'], _log=_log
        )
        # 4c. Two-pass AI enrichment: fill remaining required aspects using images + schema
        if ebay_aspect_schema and analysis.get('ai_data', {}).get('image_paths'):
            try:
                research_specs = (job_obj.ai_data or {}).get('research', {}).get('specifications')
                enriched_specifics = self.ai_agent.ai_analyzer.enrich_item_specifics(
                    image_paths=analysis['ai_data']['image_paths'][:4],
                    title=analysis['title'],
                    identification=analysis.get('ai_data', {}).get('identification', {}),
                    category_name=cat_result.get('name', ''),
                    aspect_schema=ebay_aspect_schema,
                    existing_specifics=analysis['item_specifics'],
                    research_specs=research_specs,
                )
                analysis['item_specifics'] = enriched_specifics
                _log(f"Enriched to {len(enriched_specifics)} item specifics (two-pass)")
            except Exception as e:
                _log(f"Aspect enrichment skipped: {e}", level='warning')

        # Persist category and aspect schema in ai_data
        ai_data = job_obj.ai_data or {}
        ai_data['category_id'] = cat_result.get('id')
        ai_data['category_name'] = cat_result.get('name')
        if ebay_aspect_schema:
            # Frontend uses this for required field indicators and dropdown schemas
            ai_data['ebay_aspect_schema'] = ebay_aspect_schema
            # Cleanup old key if it exists
            ai_data.pop('ebay_required_aspects', None)
        job_obj.ai_data = ai_data

        # 5. Final Pricing
        shipping_cost = analysis.get('shipping_cost')
        research_market_price = ai_data.get('research', {}).get('market_price')
        availability = ai_data.get('research', {}).get('availability')
        pricing_result = self.ai_agent.get_final_pricing(
            analysis['title'],
            condition,
            analysis['ai_suggested_price'],
            job_obj.user_price,
            shipping_cost=shipping_cost,
            log_callback=log_callback,
            identification=ai_data.get('identification'),
            research_market_price=research_market_price,
            availability=availability,
        )
        result["timing"]["pricing"] = pricing_result["timing"]

        # Persist pricing comps and reasoning for user inspection
        ai_data = job_obj.ai_data or {}
        ai_data['pricing_comps'] = pricing_result.get('comps', [])
        ai_data['pricing_reasoning'] = pricing_result.get('reasoning', '')
        ai_data['pricing_source'] = pricing_result.get('source', '')
        job_obj.ai_data = ai_data

        # 6. Image Upload (skip if cached URLs exist and no force flag)
        force_reupload = (job_obj.job_metadata or {}).get('force_image_reupload', False)
        cached_urls = (job_obj.ai_data or {}).get('image_urls', [])

        if cached_urls and not force_reupload:
            _log(f"Using {len(cached_urls)} cached image URLs (skip re-upload)")
            upload_urls = cached_urls
            result["timing"]["image_upload"] = 0.0
        else:
            ordered_images = job_obj.job_metadata.get('ordered_images') if job_obj.job_metadata else None
            upload = self.image_processor.upload_images(folder_path, ordered_filenames=ordered_images, log_callback=log_callback)
            if "error" in upload:
                return {"success": False, "error_type": "image_upload_failed", "error_message": f"Image upload failed: {upload['error']}"}
            upload_urls = upload["urls"]
            result["timing"]["image_upload"] = upload["timing"]

        # Persist uploaded image URLs in ai_data for retrieval after processing
        ai_data = job_obj.ai_data or {}
        ai_data['image_urls'] = upload_urls
        job_obj.ai_data = ai_data

        # 7. Rendering (include web research data for enriched descriptions)
        research = (job_obj.ai_data or {}).get('research', {})
        template = self._render_listing_template(
            analysis['title'], analysis['raw_description'], upload_urls,
            analysis['item_specifics'], condition, research=research
        )
        result["timing"]["templating"] = template["timing"]

        # 8. Hybrid Publishing Logic (Phase 2 Intercept)
        auto_publish = str(os.environ.get('AUTO_PUBLISH', 'false')).lower() == 'true'
        threshold_raw = float(os.environ.get('CONFIDENCE_THRESHOLD', 85))
        threshold = threshold_raw / 100 if threshold_raw > 1 else threshold_raw
        min_price = float(os.environ.get('AUTO_PUBLISH_MIN_PRICE', 15.00))

        # CATEGORY GUARD: Force review if category is missing
        missing_category = not cat_result.get('id')
        # PRICE GUARD: Force review if price is below minimum
        price_too_low = float(pricing_result.get('price', 0)) < min_price
        # REQUIRED ASPECTS GUARD: Auto-fill safe defaults, flag truly missing ones
        # eBay accepts "Does Not Apply" for generic aspects (Brand, MPN, etc.)
        # but rejects listings missing category-specific aspects (Size, Color, etc.)
        SAFE_DEFAULT_ASPECTS = {'Brand', 'MPN', 'Type', 'Model', 'UPC', 'EAN',
                                'Country/Region of Manufacture', 'California Prop 65 Warning'}
        missing_aspects = []
        if ebay_aspect_schema:
            for aspect in ebay_aspect_schema:
                name = aspect.get('name', '')
                if not aspect.get('isRequired'):
                    continue
                if name in analysis['item_specifics']:
                    continue
                if name in SAFE_DEFAULT_ASPECTS:
                    # Auto-fill with "Does Not Apply" so eBay doesn't reject
                    analysis['item_specifics'][name] = 'Does Not Apply'
                    _log(f"Auto-filled '{name}' with 'Does Not Apply'")
                else:
                    missing_aspects.append(name)
            if missing_aspects:
                _log(f"Missing {len(missing_aspects)} required aspects: {', '.join(missing_aspects)}", level='warning')

        user_approved = job_obj.job_metadata.get('user_approved', False) if job_obj.job_metadata else False

        if not user_approved and (not auto_publish or confidence_score < threshold or missing_category or price_too_low or missing_aspects):
            if missing_aspects:
                reason = f"Missing Required Aspects: {', '.join(missing_aspects[:5])}"
            elif missing_category:
                reason = "Missing Category (AI could not determine accurate eBay category)"
            elif not auto_publish:
                reason = "AUTO_PUBLISH=false"
            elif price_too_low:
                reason = f"Price Too Low (${pricing_result.get('price', 0)} < ${min_price:.2f} minimum)"
            else:
                reason = f"Low Confidence ({confidence_score:.2f} < {threshold:.2f})"
            
            _log(f"Routing to Review Queue: {reason}", level='warning')
            
            # Persist missing aspects for frontend to show
            if missing_aspects:
                ai_data = job_obj.ai_data or {}
                ai_data['missing_required_aspects'] = missing_aspects
                job_obj.ai_data = ai_data

            result.update({
                "success": True,
                "status": "pending_review",
                "price": pricing_result["price"],
                "title": analysis['title'],
                "condition": condition,
                "confidence_score": confidence_score,
                "missing_aspects": missing_aspects,
                "timing": {**result["timing"], "total": time.time() - start_time}
            })
            log_listing_result(job_obj, result, analysis, pricing_result,
                               cat_result, condition, confidence_score)
            return result

        # 9. Listing Creation (Proceed if High Confidence & Auto-Publish)
        bundle = self._create_trading_api_listing(
            title=analysis['title'], final_price=pricing_result["price"], condition=condition,
            category_id=cat_result['id'], html_description=template["html"],
            image_urls=upload_urls, item_specifics=analysis['item_specifics'],
            shipping_policy=job_obj.job_metadata.get('fulfillment_policy') if job_obj.job_metadata else None,
            scheduled_time=job_obj.scheduled_time
        )
        
        if "error" in bundle:
            error_msg = bundle["error"]
            error_type = "trading_api_error"
            if "return option" in error_msg.lower() or "shipping service" in error_msg.lower():
                error_type = "missing_policy"
            elif "token" in error_msg.lower() or "auth" in error_msg.lower():
                error_type = "auth_error"
            return {"success": False, "error_type": error_type, "error_message": error_msg}
            
        result.update({
            "success": True, "listing_id": bundle['listing_id'], "status": bundle['status'],
            "price": pricing_result["price"], "title": analysis['title'],
            "condition": condition,
            "timing": {**result["timing"], "api": bundle["timing"], "total": time.time() - start_time}
        })
        _log(f"Listing Created: {result['status']}", level='success')
        log_listing_result(job_obj, result, analysis, pricing_result,
                           cat_result, condition, confidence_score)
        return result
