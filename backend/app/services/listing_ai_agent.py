import os
from pathlib import Path
from backend.app.services.ai_analyzer import AIAnalyzer
from backend.app.services.pricing_engine import PricingEngine
from backend.app.services.ebay import taxonomy
from backend.app.core.logger import get_logger

from backend.app.core.constants import get_shipping_cost, DEFAULT_SHIPPING_COST

logger = get_logger('processor.ai')


class ListingAIAgent:
    def __init__(self):
        self.ai_analyzer = AIAnalyzer()
        self.pricing_engine = PricingEngine()
        self._default_shipping_cost = self._resolve_default_shipping_cost()

    def _resolve_default_shipping_cost(self) -> float:
        """Determine default estimated shipping cost from environment or constants."""
        try:
            return float(os.getenv('ESTIMATED_SHIPPING_COST', DEFAULT_SHIPPING_COST))
        except (ValueError, TypeError):
            return DEFAULT_SHIPPING_COST

    def _calculate_shipping_cost(self, ai_data: dict) -> float:
        """Calculate shipping cost using centralized tier logic."""
        ident = ai_data.get('identification', {})
        return get_shipping_cost(
            category_id=ident.get('category_id'),
            isbn=ident.get('isbn'),
            package_size=ident.get('package_size', ''),
            estimated_weight_lbs=ident.get('estimated_weight_lbs'),
        )

    def analyze_item(self, job_obj, images, condition, log_callback=None):
        """Perform AI vision analysis and initial pricing suggestion"""
        def _log(msg, level="info"):
            if log_callback: log_callback(msg, level)
            getattr(logger, level)(msg)

        try:
            # Check DB object for cached AI data
            force_refresh = job_obj.job_metadata.get('force_ai_refresh', False) if job_obj.job_metadata else False

            if not force_refresh and job_obj.ai_data and job_obj.ai_data.get('listing'):
                _log("Using cached AI analysis from Database")
                ai_data = job_obj.ai_data
            else:
                if force_refresh:
                    _log("Forcing AI Refresh (Ignoring Cache)...")
                _log(f"Analyzing {len(images)} images with AI (Research Mode)...")

                # Step A: Get a preliminary title or use folder name for suggestions
                temp_title = job_obj.user_title or Path(job_obj.folder_path).name
                suggestions = taxonomy.get_category_suggestions(temp_title)
                
                # Format suggestions for the prompt
                if suggestions:
                    sug_text = "Suggested eBay Categories:\n"
                    for s in suggestions[:5]:
                        sug_text += f"- ID: {s['category_id']} | Path: {s['full_path']}\n"
                else:
                    sug_text = "No eBay category suggestions found. Use your best judgment."

                seller_note = job_obj.job_metadata.get('note', '') if job_obj.job_metadata else ''
                ai_data = self.ai_analyzer.analyze_with_research(
                    images, category_suggestions=sug_text, seller_note=seller_note
                )

                if ai_data.get('error'):
                    raise Exception(f"AI Analyzer Error: {ai_data['error']}")

                # Update the job object with new AI data
                job_obj.ai_data = ai_data

            listing_data = ai_data.get('listing', {})
            if not listing_data:
                raise Exception("AI returned no output with 'listing' key")

            # Title priority: user > best of (seo_title, suggested_title) > fallback
            # SEO title is B2B-optimized (MPN-first), suggested_title is vision-based.
            # Pick the longer one — it's usually more descriptive and SEO-friendly.
            seo_title = ai_data.get('seo_title', '')
            suggested_title = listing_data.get('suggested_title', '')
            best_ai_title = max([seo_title, suggested_title], key=len) if (seo_title or suggested_title) else ''
            title = job_obj.user_title or best_ai_title or f"Item {job_obj.id}"
            raw_description = job_obj.user_description or listing_data.get('description_html') or listing_data.get('description') or f"Item {job_obj.id}"
            item_specifics = ai_data.get('item_specifics', ai_data.get('identification', {}))
            ai_suggested_price = listing_data.get('suggested_price', 0)
            
            # Extract category selection from AI
            ident = ai_data.get('identification', {})
            selected_category_id = ident.get('category_id')
            
            # Calculate dynamic shipping cost
            shipping_cost = self._calculate_shipping_cost(ai_data)

            return {
                "success": True,
                "ai_data": ai_data,
                "title": title,
                "raw_description": raw_description,
                "item_specifics": item_specifics,
                "ai_suggested_price": ai_suggested_price,
                "shipping_cost": shipping_cost,
                "category_id": selected_category_id,
                "confidence_score": listing_data.get('confidence_score', 0.85)
            }

        except Exception as e:
            logger.error(f"AI Analysis failed: {e}")
            return {"success": False, "error": str(e)}

    def get_final_pricing(self, title, condition, ai_suggested_price, user_price, shipping_cost=None, log_callback=None, identification=None, research_market_price=None, availability=None):
        """Determine the final price using research engine and user overrides.

        When free shipping is active (shipping_cost > 0), the estimated
        shipping cost is added to the suggested price so the seller's margin
        isn't eroded by shipping expenses.
        """
        def _log(msg, level="info"):
            if log_callback: log_callback(msg, level)
            getattr(logger, level)(msg)

        if user_price:
            _log(f"Using User Override Price: {user_price}")
            return {"price": str(user_price), "timing": 0,
                    "comps": [], "reasoning": "User override", "source": "user_override"}

        import time
        pricing_start = time.time()
        try:
            # Use dynamic shipping cost if provided, else fallback to default
            resolved_shipping = shipping_cost if shipping_cost is not None else self._default_shipping_cost
            
            if resolved_shipping > 0:
                _log(f"Free shipping mode: adding ${resolved_shipping:.2f} shipping buffer to price")
            
            _log("Researching pricing & comps...")
            price_result = self.pricing_engine.get_price_with_comps(
                title,
                condition=condition,
                ai_suggested_price=ai_suggested_price,
                shipping_cost=resolved_shipping,
                identification=identification,
                research_market_price=research_market_price,
                availability=availability,
            )
            final_price = str(price_result['suggested_price']) if price_result['suggested_price'] else "0.00"
            _log(f"Suggested Price: ${final_price}")
            return {
                "price": final_price,
                "timing": time.time() - pricing_start,
                "comps": price_result.get('comps', []),
                "reasoning": price_result.get('reasoning', ''),
                "source": price_result.get('source', ''),
            }
        except Exception as e:
            _log(f"Pricing Logic Failed: {e}", level='error')
            return {
                "price": "0.00",
                "warning": "Price logic failed. Manual input required.",
                "timing": time.time() - pricing_start,
                "comps": [],
                "reasoning": "",
                "source": "",
            }
