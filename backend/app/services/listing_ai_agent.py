import os
from pathlib import Path
from backend.app.services.ai_analyzer import AIAnalyzer
from backend.app.services.pricing_engine import PricingEngine
from backend.app.core.logger import get_logger

logger = get_logger('processor.ai')

# Default estimated shipping cost for free-shipping listings (USPS Ground Advantage ~1-2 lbs)
DEFAULT_SHIPPING_COST = 6.50


class ListingAIAgent:
    def __init__(self):
        self.ai_analyzer = AIAnalyzer()
        self.pricing_engine = PricingEngine()
        self._shipping_cost = self._resolve_shipping_cost()

    def _resolve_shipping_cost(self) -> float:
        """Determine estimated shipping cost to bake into the listing price.

        Reads ESTIMATED_SHIPPING_COST from .env if set, otherwise uses
        DEFAULT_SHIPPING_COST.  Set to 0 in .env to disable the buffer
        (e.g. if using a paid-shipping fulfillment policy).
        """
        env_path = Path(__file__).resolve().parents[3] / ".env"
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('ESTIMATED_SHIPPING_COST='):
                        try:
                            return float(line.split('=', 1)[1].strip())
                        except ValueError:
                            pass
        return DEFAULT_SHIPPING_COST

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
                ai_data = self.ai_analyzer.analyze_with_research(images)

                if ai_data.get('error'):
                    raise Exception(f"AI Analyzer Error: {ai_data['error']}")

                # Update the job object with new AI data
                job_obj.ai_data = ai_data

            listing_data = ai_data.get('listing', {})
            if not listing_data:
                raise Exception("AI returned no output with 'listing' key")

            title = job_obj.user_title or listing_data.get('suggested_title')
            raw_description = job_obj.user_description or listing_data.get('description_html') or listing_data.get('description') or f"Item {job_obj.id}"
            item_specifics = ai_data.get('item_specifics', ai_data.get('identification', {}))
            ai_suggested_price = listing_data.get('suggested_price', 0)

            return {
                "success": True,
                "ai_data": ai_data,
                "title": title,
                "raw_description": raw_description,
                "item_specifics": item_specifics,
                "ai_suggested_price": ai_suggested_price
            }

        except Exception as e:
            logger.error(f"AI Analysis failed: {e}")
            return {"success": False, "error": str(e)}

    def get_final_pricing(self, title, condition, ai_suggested_price, user_price, log_callback=None):
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
            return {"price": str(user_price), "timing": 0}

        import time
        pricing_start = time.time()
        try:
            if self._shipping_cost > 0:
                _log(f"Free shipping mode: adding ${self._shipping_cost:.2f} shipping buffer to price")
            _log("Researching pricing & comps...")
            price_result = self.pricing_engine.get_price_with_comps(
                title,
                condition=condition,
                ai_suggested_price=ai_suggested_price,
                shipping_cost=self._shipping_cost,
            )
            final_price = str(price_result['suggested_price']) if price_result['suggested_price'] else "0.00"
            _log(f"Suggested Price: ${final_price}")
            return {"price": final_price, "timing": time.time() - pricing_start}
        except Exception as e:
            _log(f"Pricing Logic Failed: {e}", level='error')
            return {
                "price": "0.00",
                "warning": "Price logic failed. Manual input required.",
                "timing": time.time() - pricing_start
            }
