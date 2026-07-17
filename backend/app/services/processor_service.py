"""
Listing Processor Service
Consolidates logic for creating eBay listings from folder items.
Refactored to delegate core tasks to ListingAIAgent and ImageProcessor.
"""
import os
import re
import uuid
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Optional
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
    SUPPORTED_IMAGE_EXTENSIONS,
    MEDIA_MAIL_COST,
    get_shipping_cost as get_shipping_cost_from_constants,
)

logger = get_logger('processor_service')

# A single leading positive number, optionally followed by a letter/symbol unit
# ("7", "7.5", "12 oz", "3ct", "8 oz/yd²"). Rejects ranges ("7-8"), descriptive
# text ("Mid-weight"), and "Does Not Apply".
_NUMERIC_ASPECT_RE = re.compile(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*[A-Za-z²/.]*\s*$')


def sanitize_numeric_aspects(specifics: dict, schema: list, log=None) -> None:
    """Coerce or drop NUMBER-typed eBay item specifics in place.

    eBay's Trading API rejects a listing (error 21919323) when an aspect whose
    category dataType is NUMBER carries a non-numeric value — e.g. the AI emitting
    Fabric Weight = "Mid-weight (approx. 7-8 oz)". For each such aspect we keep a
    clean positive number (rounded to 1 decimal, per eBay's format rule) or drop the
    aspect entirely. Mutates `specifics`; returns None.
    """
    if not schema:
        return
    numeric_names = {a.get('name') for a in schema
                     if (a.get('type') or '').upper() == 'NUMBER' and a.get('name')}
    for name in list(specifics.keys()):
        if name not in numeric_names:
            continue
        raw = specifics[name]
        val = raw[0] if isinstance(raw, list) else raw
        match = _NUMERIC_ASPECT_RE.match(str(val)) if val is not None else None
        num = float(match.group(1)) if match else 0.0
        if match and num > 0:
            rounded = round(num, 1)
            coerced = str(int(rounded)) if rounded == int(rounded) else str(rounded)
            if coerced != str(val) and log:
                log(f"Coerced numeric aspect: {name} = '{val}' -> '{coerced}'")
            specifics[name] = coerced
        else:
            del specifics[name]
            if log:
                log(f"Dropped non-numeric value for NUMBER aspect '{name}': '{val}'")


def _match_ngram_value(allowed_lower: dict, ngrams: list):
    """Pick the allowed value that appears earliest among the title's n-grams
    (longest match wins a tie). Strips a trailing plural/possessive so "mens" /
    "men's" match "men". Returns the original-cased value, or None."""
    matches = []  # (position, -length, original)
    for ngram, pos in ngrams:
        orig = allowed_lower.get(ngram)
        if not orig and ngram.endswith('s'):
            stripped = ngram[:-2] if ngram.endswith("'s") else ngram[:-1]
            orig = allowed_lower.get(stripped)
        if orig:
            matches.append((pos, -len(ngram), orig))
    if matches:
        matches.sort()
        return matches[0][2]
    return None


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

    @staticmethod
    def _metadata_condition(job_metadata: dict):
        """Read an explicit condition from job metadata. Mobile uploads store
        the user's choice under 'user_condition'; the folder scanner uses
        'condition'. Prefer the explicit user choice so the AI cannot override
        it (which underprices items graded above the AI's estimate)."""
        if not job_metadata:
            return None
        return job_metadata.get('user_condition') or job_metadata.get('condition')

    def _determine_condition(self, folder_path: Path, metadata_condition: str, user_condition: str, log_callback=None) -> Optional[str]:
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

        # No condition from any source — return None to trigger awaiting_condition
        _log("Condition: None (will await user input)")
        return None

    def _refine_condition_from_ai(self, current_condition: Optional[str], ai_data: dict, has_user_override: bool, has_metadata: bool, has_folder_match: bool, log_callback=None) -> Optional[str]:
        """Refine condition using AI-detected state, if no explicit override exists.

        Only upgrades/changes condition when no user override, metadata, or folder match exists.
        When current_condition is None (no source), AI detection can provide a condition
        to avoid the awaiting_condition gate.
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

    @staticmethod
    def _backfill_aspects_from_text(aspect_schema: list, specifics: dict, text: str) -> list:
        """Fill missing required and optional aspects from listing text against each aspect's
        own allowed-value list. Category-agnostic: Brand, Model, Color, Department, etc.
        Existing values are never overwritten. Returns [(name, value)].
        """
        import re
        filled = []
        text_l = f" {(text or '').lower()} "
        
        # Tokenize and clean text into lowercase words for O(1) n-gram set lookup
        words = re.findall(r'\b[\w.-]+\b', (text or '').lower())
        
        # Generate n-grams (unigrams, bigrams, trigrams) with their word indexes
        ngrams = []
        for i in range(len(words)):
            # Unigram
            ngrams.append((words[i], i))
            # Bigram
            if i < len(words) - 1:
                ngrams.append((f"{words[i]} {words[i+1]}", i))
            # Trigram
            if i < len(words) - 2:
                ngrams.append((f"{words[i]} {words[i+1]} {words[i+2]}", i))

        for aspect in aspect_schema:
            if not aspect.get('isRequired'):
                continue
            name = aspect.get('name')
            if not name or specifics.get(name):
                continue
            values = aspect.get('values') or []
            if not values:
                continue
            
            allowed_lower = {str(v).lower(): v for v in values if str(v)}
            chosen = None

            if 'size' in name.lower():
                # Numeric sizes (e.g. shoes "9.5"): only accept a number directly
                # after a size cue — a bare number in a title is usually a model code.
                m = re.search(r'\b(?:size|sz)\b[\s:]*([0-9]+(?:\.[0-9]+)?)', text_l)
                if m:
                    chosen = allowed_lower.get(m.group(1))
                if chosen is None:
                    # Word sizes (apparel "Large"/"XL") are spelled out, never after a
                    # cue, so the rule above misses them. Match them as whole title
                    # tokens — but only alphabetic values (never bare numbers) so the
                    # "don't guess a number" rule above still holds.
                    word_sizes = {k: v for k, v in allowed_lower.items()
                                  if len(k) >= 2 and any(c.isalpha() for c in k)}
                    chosen = _match_ngram_value(word_sizes, ngrams)
            else:
                # Fast n-gram set lookup against all allowed values.
                chosen = _match_ngram_value(allowed_lower, ngrams)

            if chosen is not None:
                specifics[name] = chosen
                filled.append((name, chosen))
        return filled

    def _map_research_specs_to_aspects(self, aspect_schema: list, specifics: dict, research_specs: dict, _log=None) -> None:
        """Map research specifications programmatically to eBay aspect schema.
        
        For each aspect in the schema that is not yet filled in specifics,
        we check if any key in research_specs matches the aspect name (case-insensitively,
        ignoring underscores and spaces). If a match is found:
        - If the aspect has allowed values, check if the research value matches
          or can be fuzzy matched/sub-string matched.
        - If the aspect is free-text, map the value directly.
        """
        import re
        if not research_specs or not aspect_schema:
            return

        # Build lookup of clean aspect names to their original names and allowed values
        schema_lookup = {}
        for aspect in aspect_schema:
            name = aspect.get('name')
            if not name:
                continue
            clean_name = re.sub(r'[\s_-]+', '', name.lower())
            schema_lookup[clean_name] = aspect

        for key, val in research_specs.items():
            if not val or not isinstance(val, str):
                continue
            clean_key = re.sub(r'[\s_-]+', '', key.lower())
            aspect = schema_lookup.get(clean_key)
            if not aspect:
                continue
            
            name = aspect['name']
            # Don't overwrite existing specifics
            if name in specifics and specifics[name]:
                continue

            allowed_values = aspect.get('values') or []
            if allowed_values:
                # Find matching value in allowed list
                val_lower = val.lower()
                matched_val = None
                for allowed in allowed_values:
                    allowed_lower = allowed.lower()
                    if val_lower == allowed_lower or val_lower in allowed_lower:
                        matched_val = allowed
                        break
                
                if matched_val:
                    specifics[name] = matched_val
                    if _log:
                        _log(f"Mapped research spec (allowed): {name} = '{val}' -> '{matched_val}'")
            else:
                # Free text aspect
                specifics[name] = val[:65]
                if _log:
                    _log(f"Mapped research spec (free text): {name} = '{val}'")

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

    def _create_trading_api_listing(self, title: str, final_price: str, condition: str, category_id: str, html_description: str, image_urls: list, item_specifics: dict, shipping_policy: str, scheduled_time: str = None, estimated_weight_lbs=None, best_offer_decline_pct=None) -> dict:
        """Create eBay Listing via Trading API"""
        timing_start = time.time()
        sku = 'DC-' + uuid.uuid4().hex[:8].upper()
        
        try:
            title = validate_title(title[:TITLE_MAX_LENGTH])
            final_price = str(validate_price(final_price))
            condition = validate_condition(condition)
            generic_id = CONDITION_ID_MAP.get(condition, '3000')

            # Resolve to the category's actual condition id. Graded categories
            # (shoes/apparel/bags) map USED_EXCELLENT to 'Pre-owned - Excellent'
            # (e.g. 2990), not generic 3000 which displays as 'Good' there.
            from backend.app.services.ebay.taxonomy import resolve_condition_id
            condition_id = resolve_condition_id(condition, category_id, generic_id)
            if condition_id != generic_id:
                logger.info(f"Condition resolved: {condition} ({generic_id}) -> {condition_id} for category {category_id}")

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
                'item_location': os.environ.get('EBAY_ITEM_LOCATION', 'Clovis, CA'),
                'weight_lbs': estimated_weight_lbs
            }

            from backend.app.core.settings_manager import get_settings_manager
            settings_mgr = get_settings_manager()
            if str(settings_mgr.get('BEST_OFFER_ENABLED', 'true')).lower() == 'true':
                price_f = float(final_price)
                accept_pct = float(settings_mgr.get('BEST_OFFER_AUTO_ACCEPT_PCT', '90') or 90)
                # Discovery listings pass a looser floor so lowball-but-real
                # offers surface instead of being auto-declined.
                decline_pct = (best_offer_decline_pct if best_offer_decline_pct is not None
                               else float(settings_mgr.get('BEST_OFFER_AUTO_DECLINE_PCT', '60') or 60))
                item_data.update({
                    'best_offer_enabled': True,
                    'best_offer_auto_accept': round(price_f * accept_pct / 100, 2),
                    'best_offer_minimum': round(price_f * decline_pct / 100, 2),
                })

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
        metadata_condition = self._metadata_condition(job_obj.job_metadata)
        condition = self._determine_condition(folder_path, metadata_condition, job_obj.user_condition, log_callback)
        has_user_override = bool(job_obj.user_condition)
        has_metadata = bool(metadata_condition)
        has_folder_match = folder_path.parent.name in CONDITION_MAP

        # 2. Images
        images = sorted([f for f in folder_path.iterdir() if f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS])
        if not images:
            return {"success": False, "error_type": "no_images", "error_message": "No images found"}

        # 3. AI Analysis — outer timeout so one hung Gemini request can't
        # block the single queue worker forever. The abandoned worker thread
        # is leaked (can't be killed), but the queue moves on.
        ai_timeout = int(os.environ.get('AI_ANALYSIS_TIMEOUT', '300'))
        ai_start = time.time()
        ai_pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = ai_pool.submit(
                self.ai_agent.analyze_item,
                job_obj, [str(img) for img in images], condition, log_callback
            )
            analysis = future.result(timeout=ai_timeout)
        except FuturesTimeoutError:
            result["timing"]["ai_analysis"] = time.time() - ai_start
            _log(f"AI analysis timed out after {ai_timeout}s", level='error')
            return {"success": False, "error_type": "ai_analysis_timeout",
                    "error_message": f"AI analysis exceeded {ai_timeout}s"}
        finally:
            ai_pool.shutdown(wait=False, cancel_futures=True)
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
        # 4bc. Programmatic research spec mapper: fill empty specifics from web research before AI second pass
        research_specs = (job_obj.ai_data or {}).get('research', {}).get('specifications')
        if research_specs and ebay_aspect_schema:
            try:
                self._map_research_specs_to_aspects(
                    ebay_aspect_schema, analysis['item_specifics'], research_specs, _log=_log
                )
            except Exception as e:
                _log(f"Programmatic research mapping skipped: {e}", level='warning')
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

        # --- PHASE 1 GATE: Pause if no condition determined ---
        if condition is None:
            _log("No condition determined -- pausing for user input", level='warning')
            result.update({
                "success": True,
                "status": "awaiting_condition",
                "title": analysis['title'],
                "category_id": cat_result.get('id'),
                "category_name": cat_result.get('name', ''),
                "confidence_score": confidence_score,
                "timing": {**result["timing"], "total": time.time() - start_time}
            })
            return result

        # 5. Final Pricing
        # Recalculate shipping now that category is known (books get Media Mail rate)
        ident = ai_data.get('identification', {})
        shipping_cost = get_shipping_cost_from_constants(
            category_id=cat_result.get('id'),
            isbn=ident.get('isbn'),
            package_size=ident.get('package_size', ''),
            estimated_weight_lbs=ident.get('estimated_weight_lbs'),
        )
        ai_data['shipping_cost'] = shipping_cost
        ai_data['shipping_method'] = 'media_mail' if shipping_cost == MEDIA_MAIL_COST else 'standard'
        job_obj.ai_data = ai_data
        research_market_price = ai_data.get('research', {}).get('market_price')
        availability = ai_data.get('research', {}).get('availability')
        seller_note = job_obj.job_metadata.get('note', '') if job_obj.job_metadata else ''
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
            seller_note=seller_note,
        )
        result["timing"]["pricing"] = pricing_result["timing"]

        # Price floor guard: weak pricing signals (e.g. eBay comp-scraper 403 -> no comps ->
        # AI estimate defaulting to 0) can yield an invalid/too-low price that eBay rejects
        # with Trading API error 73 ("below the minimum price of FIXED_PRICE"). Clamp to
        # DEFAULT_PRICE so the listing still succeeds; flag it so the user can review.
        from backend.app.core.constants import MIN_LISTING_PRICE
        try:
            _priced = float(pricing_result.get("price") or 0)
        except (TypeError, ValueError):
            _priced = 0.0
        if _priced < MIN_LISTING_PRICE:
            _fallback_price = float(os.getenv('DEFAULT_PRICE', '29.99'))
            _log(f"Price ${_priced:.2f} below floor ${MIN_LISTING_PRICE} (weak pricing signal) "
                 f"-> using DEFAULT_PRICE ${_fallback_price:.2f}; review before go-live", level='warning')
            pricing_result["price"] = _fallback_price
            pricing_result["price_floored"] = True

        # Persist pricing comps and reasoning for user inspection
        ai_data = job_obj.ai_data or {}
        ai_data['pricing_comps'] = pricing_result.get('comps', [])
        ai_data['pricing_reasoning'] = pricing_result.get('reasoning', '')
        ai_data['pricing_source'] = pricing_result.get('source', '')
        ai_data['pricing_confidence'] = pricing_result.get('confidence')
        ai_data['pricing_confidence_reason'] = pricing_result.get('confidence_reason')
        if pricing_result.get('comp_price') is not None and pricing_result.get('ai_price') is not None:
            # Comps-vs-AI conflict: both numbers surface in the Review Queue.
            ai_data['pricing_conflict'] = {
                'comp_price': pricing_result.get('comp_price'),
                'ai_price': pricing_result.get('ai_price'),
            }
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
        job_obj.description = template["html"]
        result["timing"]["templating"] = template["timing"]

        # 8. Required-aspects completion (NO-BLOCKS ENGINE)
        # REQUIRED ASPECTS GUARD: Auto-fill safe defaults, resolve the rest (below).
        # eBay accepts "Does Not Apply" for generic aspects (Brand, MPN, etc.)
        # but rejects listings missing category-specific aspects (Size, Color, etc.) —
        # those get resolved instead of routed to review.
        SAFE_DEFAULT_ASPECTS = {'Brand', 'MPN', 'Type', 'Model', 'UPC', 'EAN',
                                'Country/Region of Manufacture', 'California Prop 65 Warning'}
        missing_aspects = []
        if ebay_aspect_schema:
            # Backfill required/optional aspects the AI missed from
            # the title + identification text before flagging anything as missing.
            ident = analysis.get('ai_data', {}).get('identification', {}) or {}
            backfill_text = ' '.join(str(v) for v in [
                analysis.get('title', ''),
                ident.get('brand', ''), ident.get('model', ''),
                ident.get('product_type', ''),
                analysis.get('raw_description', ''),
            ] if v)
            backfilled = self._backfill_aspects_from_text(
                ebay_aspect_schema, analysis['item_specifics'], backfill_text
            )
            for name, value in backfilled:
                _log(f"Backfilled aspect from title: {name} = {value}")

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
                # NO-BLOCKS ENGINE: resolve the last missing required aspects instead of
                # routing to review. eBay allowed-values -> batched Gemini -> safe default;
                # guarantees every required aspect is valued so the listing never blocks.
                _log(f"Resolving {len(missing_aspects)} missing required aspects: {', '.join(missing_aspects)}")
                missing_specs = [a for a in ebay_aspect_schema
                                 if a.get('isRequired') and a.get('name') in missing_aspects]
                try:
                    resolved = self.ai_agent.ai_analyzer.resolve_missing_required_aspects(
                        missing=missing_specs,
                        title=analysis['title'],
                        identification=ai_data.get('identification', {}) or {},
                        category_name=cat_result.get('name', ''),
                        image_paths=(analysis.get('ai_data', {}).get('image_paths') or [])[:4],
                        research_specs=(job_obj.ai_data or {}).get('research', {}).get('specifications'),
                    )
                except Exception as e:
                    _log(f"Aspect resolver error (using safe defaults): {e}", level='warning')
                    resolved = {}
                auto_filled = {}
                for name, info in resolved.items():
                    analysis['item_specifics'][name] = info['value']
                    auto_filled[name] = info
                    _log(f"Auto-resolved: {name} = {info['value']} ({info['source']}, conf {info['confidence']:.2f})")
                ai_data = job_obj.ai_data or {}
                ai_data['auto_filled_aspects'] = auto_filled
                ai_data.pop('missing_required_aspects', None)  # nothing is "missing" anymore
                job_obj.ai_data = ai_data
                missing_aspects = []  # resolver guarantees fill

        # CATEGORY FALLBACK: never block on a missing category.
        if not cat_result.get('id'):
            cat_result['id'] = DEFAULT_CATEGORY_ID
            _log(f"No category determined -> fallback {DEFAULT_CATEGORY_ID}", level='warning')

        # NO REVIEW GATE (fully-auto): data is guaranteed complete, so the item lists
        # itself. Capture is the only human step. A genuine error during listing
        # creation below is the only path to "Needs you".

        # 9. Listing Creation
        # Auto-schedule at optimal traffic time if no manual schedule set.
        # Default ON (AUTO_SCHEDULE_OPTIMAL) — posts at peak traffic and gives a
        # quiet cancel window; set AUTO_SCHEDULE_OPTIMAL=false to list immediately.
        listing_schedule_time = job_obj.scheduled_time
        if not listing_schedule_time:
            auto_schedule = str(os.environ.get('AUTO_SCHEDULE_OPTIMAL', 'true')).lower() == 'true'
            if auto_schedule:
                from backend.app.core.constants import get_next_optimal_listing_time
                listing_schedule_time = get_next_optimal_listing_time()
                _log(f"Auto-scheduled for peak traffic: {listing_schedule_time}")

        # Final gate: NUMBER-typed aspects must be a clean positive number or eBay
        # rejects the whole listing (error 21919323). Runs after all enrich/backfill/
        # resolve passes so a late text value (e.g. "Does Not Apply") can't slip through.
        sanitize_numeric_aspects(analysis['item_specifics'], ebay_aspect_schema, log=_log)

        # LISTING-QUALITY GUARDRAILS: title hygiene + brand/aspect normalization
        # are auto-fixed in place; price sanity (no-comp outlier, or >3x comp
        # median) is a judgment call that routes to pending_review instead of
        # submitting to eBay. Runs on job_obj (the guardrail's contract), so
        # stage the current title/specifics onto it, then read the (possibly
        # cleaned) values back for submission.
        from backend.app.services.listing_guardrails import apply_pre_listing_guardrails
        job_obj.title = analysis['title']
        job_obj.item_specifics = analysis['item_specifics']
        guardrail_result = apply_pre_listing_guardrails(
            job_obj,
            price=pricing_result.get('price'),
            source=pricing_result.get('source'),
            comps=pricing_result.get('comps'),
            confidence=pricing_result.get('confidence'),
            confidence_reason=pricing_result.get('confidence_reason'),
        )
        analysis['title'] = job_obj.title
        analysis['item_specifics'] = job_obj.item_specifics

        review_reason = guardrail_result.get('review_reason')
        if review_reason and (job_obj.job_metadata or {}).get('user_approved'):
            # The approve endpoints set user_approved exactly so an approved
            # job doesn't bounce back here — the guardrail re-fires on
            # reprocess (same price, same missing comps) and without this
            # override the job ping-pongs between approval and review forever.
            _log(f"Guardrail flag overridden by prior user approval: {review_reason}",
                 level='warning')
            review_reason = None
        best_offer_decline_pct = None
        if review_reason:
            # Price-discovery mode: a no-comp item (commercial parts etc.)
            # lists HIGH with Best Offer + aggressive markdown tag instead of
            # stalling in review. Must sit AFTER the user_approved bypass so
            # an approved price is never re-priced. Conflicts/dups/unpriceable
            # items fall through to the review routing below.
            from backend.app.core.settings_manager import get_settings_manager
            from backend.app.services.price_discovery import (
                is_discovery_eligible, compute_discovery_price,
            )
            settings_mgr = get_settings_manager()
            discovery_enabled = str(settings_mgr.get(
                'PRICE_DISCOVERY_ENABLED', 'true')).lower() == 'true'
            if is_discovery_eligible(pricing_result, discovery_enabled):
                markup_pct = float(settings_mgr.get('PRICE_DISCOVERY_MARKUP_PCT', '25') or 25)
                discovery = compute_discovery_price(
                    pricing_result, job_obj.ai_data, markup_pct)
                if discovery:
                    _log(f"Price discovery: listing at ${discovery['list_price']:.2f} "
                         f"({discovery['basis']}) instead of review hold ({review_reason})")
                    if not job_obj.job_metadata:
                        job_obj.job_metadata = {}
                    job_obj.job_metadata['price_discovery'] = {
                        'started_at': time.time(),
                        'base_price': float(pricing_result.get('price') or 0),
                        'list_price': discovery['list_price'],
                        'basis': discovery['basis'],
                        'reason': review_reason,
                    }
                    pricing_result['price'] = f"{discovery['list_price']:.2f}"
                    best_offer_decline_pct = float(settings_mgr.get(
                        'PRICE_DISCOVERY_DECLINE_PCT', '50') or 50)
                    from backend.app.services.whatsapp_notify import (
                        get_notify_destination, notify_whatsapp,
                        build_price_discovery_message,
                    )
                    dest = get_notify_destination(job_obj.job_metadata)
                    if dest:
                        notify_whatsapp(dest, build_price_discovery_message(
                            analysis['title'], discovery['list_price'],
                            discovery['basis']))
                    review_reason = None
        if review_reason:
            # Pause + tell me: the job holds in the Review Queue AND the user
            # gets a WhatsApp text (originating chat for bridge jobs, else the
            # owner chat from WHATSAPP_NOTIFY_CHAT_ID). This replaced the old
            # "list anyway" auto-decide — a text makes the review visible, so
            # pausing no longer strands WhatsApp items invisibly.
            from backend.app.services.whatsapp_notify import (
                get_notify_destination, notify_whatsapp, build_price_review_message,
            )
            _log(f"Price flagged for review: {review_reason}", level='warning')
            dest = get_notify_destination(job_obj.job_metadata)
            if dest:
                notify_whatsapp(dest, build_price_review_message(
                    analysis['title'],
                    pricing_result.get('price'),
                    pricing_result.get('comp_price'),
                    pricing_result.get('ai_price'),
                    review_reason,
                ))
                try:
                    # Marker gates the Hermes plugin's reply-to-approve
                    # commands (ok / price / skip) for this chat.
                    from backend.app.services.review_reply import append_review_marker
                    append_review_marker(
                        current_app.config.get('CAPTURES_DIR'),
                        dest.get('chat_id'), getattr(job_obj, 'id', None))
                except Exception as e:
                    _log(f"Review marker write failed (non-fatal): {e}", level='warning')
            result.update({
                "success": True,
                "status": "pending_review",
                "title": analysis['title'],
                "price": pricing_result.get('price'),
                "condition": condition,
                "confidence_score": confidence_score,
                "error_message": review_reason,
                "timing": {**result["timing"], "total": time.time() - start_time},
            })
            return result

        bundle = self._create_trading_api_listing(
            title=analysis['title'], final_price=pricing_result["price"], condition=condition,
            category_id=cat_result['id'], html_description=template["html"],
            image_urls=upload_urls, item_specifics=analysis['item_specifics'],
            shipping_policy=job_obj.job_metadata.get('fulfillment_policy') if job_obj.job_metadata else None,
            best_offer_decline_pct=best_offer_decline_pct,
            scheduled_time=listing_schedule_time,
            estimated_weight_lbs=(analysis.get('ai_data', {}).get('identification', {}) or {}).get('estimated_weight_lbs')
        )
        
        if "error" in bundle:
            error_msg = bundle["error"]
            error_type = "trading_api_error"
            if "return option" in error_msg.lower() or "shipping service" in error_msg.lower():
                error_type = "missing_policy"
            elif "token" in error_msg.lower() or "auth" in error_msg.lower():
                error_type = "auth_error"
            return {"success": False, "error_type": error_type, "error_message": error_msg}

        # PROMOTED LISTINGS HOOK
        from backend.app.core.settings_manager import get_settings_manager
        settings_mgr = get_settings_manager()
        is_promoted = str(settings_mgr.get('PROMOTED_LISTINGS_ENABLED', 'false')).lower() == 'true'
        if is_promoted and bundle.get('listing_id'):
            try:
                ad_rate = float(settings_mgr.get('PROMOTED_LISTINGS_AD_RATE', '5.0'))
                from backend.app.services.ebay.marketing import MarketingAPI
                marketing_api = MarketingAPI()
                promo_res = marketing_api.promote_listing(bundle['listing_id'], ad_rate)
                if promo_res.get('success'):
                    _log(f"Successfully promoted listing {bundle['listing_id']} at {ad_rate}%", level='success')
                else:
                    _log(f"Failed to promote listing {bundle['listing_id']}: {promo_res.get('error')}", level='warning')
            except Exception as e:
                _log(f"Error promoting listing {bundle['listing_id']}: {e}", level='warning')
            
        result.update({
            "success": True, "listing_id": bundle['listing_id'], "status": bundle['status'],
            "price": pricing_result["price"], "title": analysis['title'],
            "description": template["html"],
            "condition": condition,
            "scheduled_time": listing_schedule_time,
            "timing": {**result["timing"], "api": bundle["timing"], "total": time.time() - start_time}
        })
        _log(f"Listing Created: {result['status']}", level='success')
        log_listing_result(job_obj, result, analysis, pricing_result,
                           cat_result, condition, confidence_score)
        return result
