"""
Pricing Engine for eBay Draft Commander
Uses eBay Browse API for market-based pricing
"""
import math
import os
import json
import re
import statistics
from typing import List, Dict, Optional, Union, Any
from urllib.parse import quote
from backend.app.core.constants import (
    AI_PRICING_MODEL,
    EBAY_FINAL_VALUE_FEE_RATE,
    EBAY_PAYMENT_PROCESSING_FEE,
    MIN_LISTING_PRICE,
    MAX_LISTING_PRICE,
    RARITY_PERCENTILE_THRESHOLD,
)
from backend.app.core.logger import get_logger

logger = get_logger('pricing_engine')


def format_price_source(source: str, comp_count: int = 0) -> str:
    """Convert internal price source key to human-readable label."""
    count_str = f"{comp_count} " if comp_count > 0 else ""
    labels = {
        'market_data_isbn': f'Based on {count_str}listings (ISBN match)',
        'market_data_id': f'Based on {count_str}listings (ID match)',
        'market_data_alt_pn': f'Based on {count_str}listings (alt part #)',
        'market_data_keyword': f'Based on {count_str}listings',
        'market_data': f'Based on {count_str}listings',
        'research_market_price': 'AI web research estimate',
        'ai_grounded_research': 'AI web research estimate (search grounded)',
        'ai_grounding': 'AI estimate (no comp data)',
        'ai_estimate': 'AI vision estimate (lowest confidence)',
        'ai_vision': 'AI vision estimate (lowest confidence)',
        'user_override': 'Manual price',
    }
    return labels.get(source, source)


class PricingEngine:
    """Calculates suggested prices using eBay Browse API and AI fallbacks.

    See get_price_with_comps() for the full pricing cascade.
    """
    
    def __init__(self):
        """Initialize with eBay App ID and Google API key from environment"""
        self.app_id = os.getenv('EBAY_APP_ID')

        if not self.app_id:
            logger.warning("[WARN] EBAY_APP_ID not found - Pricing Intelligence disabled")

        # Initialize Gemini 3 for Search Grounding (from Roadmap Phase 6)
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
            
        self.ai_client = None
        if self.google_api_key:
            try:
                from google import genai
                self.ai_client = genai.Client(api_key=self.google_api_key)
                logger.info(f"[OK] Pricing AI initialized ({AI_PRICING_MODEL} + Search Grounding)")
            except Exception as e:
                logger.warning(f"[WARN] Could not initialize Pricing AI: {e}")
    
    @staticmethod
    def _smart_round_99(price: float) -> float:
        """Round a price to the nearest .99 ending without inflating aggressively.

        Rules (only for prices > $10):
        - If cents >= 0.80, round UP to current dollar .99 ($44.85 -> $44.99)
        - Otherwise round DOWN to previous dollar .99 ($44.32 -> $43.99)
        """
        if price <= 15:
            return price
        base = math.floor(price)
        cents = price - base
        if cents >= 0.80:
            return base + 0.99
        return base - 0.01

    @staticmethod
    def _sanitize_price(price: Optional[float]) -> float:
        """Guard against NaN, infinity, and out-of-bounds prices.

        Always returns a valid float. Falls back to DEFAULT_PRICE for None/invalid inputs.
        """
        if price is None:
            return float(os.getenv('DEFAULT_PRICE', '29.99'))
        if math.isnan(price) or math.isinf(price):
            logger.error(f"Price calculation produced invalid value: {price}, using default")
            return float(os.getenv('DEFAULT_PRICE', '29.99'))
        if price < MIN_LISTING_PRICE:
            return MIN_LISTING_PRICE
        if price > MAX_LISTING_PRICE:
            return MAX_LISTING_PRICE
        return price

    def search_sold_listings(self, keywords: str, category_id: Optional[str] = None, limit: int = 15, condition: str = None) -> List[Dict[str, Any]]:
        """
        Search for items matching the keywords via Browse API.

        Args:
            keywords: Search query (e.g., "NTTAT CLETOP")
            category_id: Optional eBay category ID to narrow search
            limit: Max number of results (1-100)
            condition: Optional condition enum for Browse API filtering

        Returns:
            List of dicts with: title, price, condition, end_date, url
        """
        if not self.app_id:
            return []

        # Use eBayResearcher (Browse API) with condition filtering
        try:
            from backend.app.services.ebay.researcher import eBayResearcher
            researcher = eBayResearcher(use_api=True, use_ai=False) # AI fallback handled by caller if needed

            # The researcher returns {'items': [SoldItem...], ...}
            # We need to adapt it to the dict format expected by this class
            results = researcher.search_sold(keywords, limit=limit, condition=condition)
            
            sold_items = []
            if results and 'items' in results:
                for item in results['items']:
                    sold_items.append({
                        "title": item['title'],
                        "price": item['price'],
                        "currency": "USD", # Researcher normalizes to float, assuming USD for now
                        "condition": item['condition'],
                        "end_date": item['date'],
                        "url": item['url']
                    })
            
            return sold_items

        except ImportError:
            logger.error("[FAIL] Could not import eBayResearcher")
            return []
        except Exception as e:
            logger.error(f"[FAIL] Pricing engine error (using Researcher): {e}")
            return []
    
    MIN_TITLE_SIMILARITY = 0.30  # Minimum word overlap ratio
    MIN_COMPS_AFTER_FILTER = 3   # Don't filter below this count

    def filter_comps(self, comps: List[Dict], reference_title: str) -> List[Dict]:
        """Filter comps by title similarity and price outlier rejection.

        1. Title similarity: keep comps sharing >= 30% of words with reference title
        2. Outlier rejection: drop prices > 2 std devs from median
        3. Safety: never filter below MIN_COMPS_AFTER_FILTER if we started with enough
        """
        if len(comps) <= self.MIN_COMPS_AFTER_FILTER:
            return comps

        # --- Phase 1: Title similarity ---
        ref_words = set(reference_title.lower().split())
        scored = []
        for comp in comps:
            comp_words = set(comp.get("title", "").lower().split())
            if not ref_words or not comp_words:
                scored.append((0.0, comp))
                continue
            overlap = len(ref_words & comp_words) / max(len(ref_words), 1)
            scored.append((overlap, comp))

        scored.sort(key=lambda x: x[0], reverse=True)
        title_filtered = [c for sim, c in scored if sim >= self.MIN_TITLE_SIMILARITY]

        if len(title_filtered) < self.MIN_COMPS_AFTER_FILTER:
            title_filtered = [c for _, c in scored[:self.MIN_COMPS_AFTER_FILTER]]

        # --- Phase 2: Outlier rejection ---
        if len(title_filtered) >= 5:
            prices = [c["price"] for c in title_filtered if c.get("price", 0) > 0]
            if prices:
                median = statistics.median(prices)
                try:
                    stdev = statistics.stdev(prices)
                except statistics.StatisticsError:
                    stdev = 0
                if stdev > 0:
                    lower = median - 2 * stdev
                    upper = median + 2 * stdev
                    outlier_filtered = [c for c in title_filtered if lower <= c.get("price", 0) <= upper]
                    if len(outlier_filtered) >= self.MIN_COMPS_AFTER_FILTER:
                        title_filtered = outlier_filtered

        return title_filtered

    def calculate_suggested_price(self, sold_items: List[Dict], our_condition: str = "Used - Good", acquisition_cost: float = 0.0, shipping_cost: float = 0.0, availability: str = None) -> Dict[str, Any]:
        """
        Calculate a suggested price based on sold items data.

        Uses median price (robust to outliers) with condition adjustment.
        Also performs margin protection check against acquisition cost.
        When shipping_cost > 0 (free shipping mode), the cost is added to
        the suggested price so the seller doesn't eat shipping margin.

        Args:
            sold_items: List of dicts from search_sold_listings()
            our_condition: The condition of our item
            acquisition_cost: Cost of goods sold (default 0.0)
            shipping_cost: Estimated shipping cost to bake into price (default 0.0)

        Returns:
            Dict with: suggested_price, comp_count, median_price, reasoning, margin_data
        """
        if not sold_items:
            return {
                "suggested_price": None,
                "comp_count": 0,
                "median_price": None,
                "reasoning": "No comparable sales found"
            }
        
        prices = [item["price"] for item in sold_items if item["price"] > 0]

        if not prices:
            return {
                "suggested_price": None,
                "comp_count": 0,
                "median_price": None,
                "reasoning": "No valid prices in comps"
            }

        # Calculate median (robust to outliers)
        median_price = statistics.median(prices)

        # For rare/very_rare items, use 75th percentile instead of median
        sorted_prices = sorted(prices)
        if availability in ('rare', 'very_rare'):
            idx = int(len(sorted_prices) * RARITY_PERCENTILE_THRESHOLD / 100)
            base_price = sorted_prices[min(idx, len(sorted_prices) - 1)]
            reasoning_prefix = "75th pctl (rare)"
        else:
            base_price = median_price
            reasoning_prefix = "Median"

        # Use base_price directly — condition filtering is handled by the
        # Browse API query, so comps already match our condition bucket.
        suggested_price = round(base_price, 2)

        # --- Free Shipping Buffer ---
        # When offering free shipping, bake the estimated shipping cost into the price
        shipping_buffered = False
        if shipping_cost > 0:
            suggested_price = round(suggested_price + shipping_cost, 2)
            shipping_buffered = True

        # --- Margin Protection ---
        # Estimated eBay Fees: ~13.25% + $0.30
        est_fees = (suggested_price * EBAY_FINAL_VALUE_FEE_RATE) + EBAY_PAYMENT_PROCESSING_FEE
        projected_profit = suggested_price - est_fees - acquisition_cost - shipping_cost
        
        min_margin = 10.00 # Minimum desired profit per item
        margin_boost = False
        
        if acquisition_cost > 0 and projected_profit < min_margin:
            # Price is too low for target margin, calculate target price
            # Target = (Cost + MinMargin + ProcessingFee) / (1 - FVF)
            target_price = (acquisition_cost + min_margin + EBAY_PAYMENT_PROCESSING_FEE) / (1 - EBAY_FINAL_VALUE_FEE_RATE)
            suggested_price = round(target_price, 2)
            margin_boost = True
            
        # Smart pricing: round to nearest .99 without aggressive inflation
        suggested_price = self._smart_round_99(suggested_price)

        # Sanitize: guard against NaN/infinity and enforce price bounds
        suggested_price = self._sanitize_price(suggested_price)

        reasoning = f"{reasoning_prefix} of {len(prices)} listings (${base_price:.2f})"
        if shipping_buffered:
            reasoning += f" + ${shipping_cost:.2f} shipping"
        if margin_boost:
            reasoning += f" (Boosted for ${min_margin} min margin)"

        return {
            "suggested_price": suggested_price,
            "comp_count": len(prices),
            "median_price": round(median_price, 2),
            "reasoning": reasoning,
            "projected_profit": round(suggested_price - est_fees - acquisition_cost - shipping_cost, 2)
        }
    
    def generate_ebay_search_link(self, title: str) -> str:
        """
        Generate a link to eBay's sold listings search for manual research.
        
        Args:
            title: Item title to search
        
        Returns:
            URL string
        """
        # Clean title for URL
        search_terms = "+".join(title.split()[:6])
        return f"https://www.ebay.com/sch/i.html?_nkw={quote(search_terms)}&LH_Complete=1&LH_Sold=1"
    
    def get_ai_price_estimate(self, title: str, condition: str) -> Optional[Dict[str, Union[float, str]]]:
        """Estimate price using Gemini with Google Search grounding"""
        if not self.ai_client:
            return None
            
        try:
            from google.genai import types
            
            # IMPORTANT: Search Grounding + JSON Mode often conflicts (INVALID_ARGUMENT).
            # We must use TEXT mode and parse the JSON out manually.
            
            prompt = f"""You are a High-End Industrial Appraiser and eBay Pricing Strategist.
            The user has an item that may be rare, industrial, or undervalued.
            Do NOT default to a low price just because direct sales data is scarce.
            IMPORTANT: Return the BASE market value only. Do NOT include ANY shipping
            costs or shipping buffers. Shipping is handled separately by the caller.

            Item Title: {title}
            Condition: {condition}
            
            YOUR MISSION: Determine the maximum realistic list price.
            
            EXECUTE CHAIN OF THOUGHT (Do not skip steps):
            
            PHASE 1: IDENTIFY & ANCHOR (The most important step)
            1. What EXACTLY is this? (e.g., "Precision Fiber Optic Cleaner", "Vintage Telescope", "Industrial PLC").
            2. Who acts as the buyer? (Engineers, Factories, Collectors?). These buyers pay more.
            3. SEARCH for the ORIGINAL MSRP or Current Retail Price of this item (or its nearest modern equivalent).
               -> This is your "ANCHOR PRICE". If it cost $500 new, it is likely NOT worth $15 used, closer to $100-$200.
            
            PHASE 2: MARKET REALITY
            1. Search for used sold listings on eBay/Mercari.
            2. IF you find cheap sold comps ($10-$20), CHECK: Are they "For Parts"? Broken? Generic Clones?
            3. IF offered item is genuine/good condition, IGNORE low-quality outliers.
            
            PHASE 3: VALUATION CALCULATION
            - If Direct Comps exist and match condition: Use them.
            - If NO Direct Comps: Apply "Depreciation Logic" to your ANCHOR MSRP:
                 * New/Open Box: 70-80% of MSRP
                 * Used Good: 40-60% of MSRP
                 * Vintage/Rare: May maintain or exceed MSRP.
            
            OUTPUT:
            Return a JSON block:
            ```json
            {{
                "identified_item": "Brief description of what it is",
                "original_msrp_estimate": "$0.00",
                "listing_strategy": "Value based on [Comps|MSRP Depreciation]",
                "price": 0.00,
                "reasoning": "Step-by-step logic: 1. MSRP was $X. 2. Comps are scarce but similar industrial units sell for $Y. 3. Setting price to $Z to capture professional value."
            }}
            ```
            """
            
            response = self.ai_client.models.generate_content(
                model=AI_PRICING_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3
                    # response_mime_type REMOVED to enable Search Tool
                )
            )
            
            # Parse Text Response
            text = response.text.strip() if response.text else ""
            
            # Extract JSON block
            match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                # Try finding strict JSON without ticks
                match = re.search(r'\{.*"price":.*\}', text, re.DOTALL)
                if match:
                     data = json.loads(match.group(0))
                else:
                     raise ValueError("No JSON found in AI response")

            price = float(data.get('price', 0))
            reasoning = data.get('reasoning', 'AI Estimate')
            
            if price > 0:
                return {"price": price, "reasoning": reasoning}
                
        except Exception as e:
            logger.warning(f"   [WARN] Gemini Grounding failed: {e}")
            
            # FALLBACK: Try Standard Inference (No Tools) if Grounding crashes
            try:
                logger.info("   [RETRY] Retrying with robust logical inference (No Search Tools)...")
                retry_prompt = f"""You are an expert appraiser. valid_price_prediction_required.
                Item: {title}
                Condition: {condition}
                
                Based on your internal knowledge of this item brand and type, estimate a fair market listing price for eBay.
                If it is a rare or industrial item, value it appropriately (do not undervalue).
                
                Return JSON:
                {{
                    "price": 0.00,
                    "reasoning": "Inferred based on brand reputation and device type"
                }}"""
                
                retry_resp = self.ai_client.models.generate_content(
                    model=AI_PRICING_MODEL,
                    contents=retry_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        response_mime_type="application/json"
                    )
                )
                
                text = retry_resp.text.strip()
                if text.startswith('```json'):  # parse json if wrapped
                    text = text.split('```json')[1].split('```')[0]
                elif text.startswith('```'):
                    text = text.split('```')[1].split('```')[0]

                data = json.loads(text)
                return {"price": float(data.get('price', 0)), "reasoning": "Inferred: " + data.get('reasoning', '')}
            except Exception as e2:
                logger.error(f"   [FAIL] Standard Inference also failed: {e2}")

        return None

    def _build_keyword_query(self, title: str, identification: Optional[Dict] = None) -> str:
        """Build an optimized search query from identifiers or title.

        Priority:
        1. Brand + MPN (most precise, what buyers search by)
        2. Brand + Model (good fallback)
        3. First 8 words of title (last resort)
        """
        if identification:
            brand = identification.get('brand', '').strip()
            mpn = identification.get('mpn', '').strip()
            model = identification.get('model', '').strip()
            product_type = identification.get('product_type', '').strip()

            # Strategy: brand + mpn + product_type
            if brand and mpn:
                parts = [brand, mpn]
                if product_type and len(" ".join(parts + [product_type])) <= 60:
                    parts.append(product_type)
                return " ".join(parts)

            # Strategy: brand + model
            if brand and model:
                parts = [brand, model]
                if product_type and len(" ".join(parts + [product_type])) <= 60:
                    parts.append(product_type)
                return " ".join(parts)

        # Fallback: first 8 words of title
        return " ".join(title.split()[:8])

    def get_price_with_comps(self, title: str, condition: str = "Used - Good", category_id: Optional[str] = None, ai_suggested_price: Optional[str] = None, acquisition_cost: float = 0.0, isbn: Optional[str] = None, shipping_cost: float = 0.0, identification: Optional[Dict] = None, research_market_price: Optional[Dict] = None, availability: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point: Get suggested price and comparable sales data.

        Pricing cascade (in priority order):
        0. User override (handled by caller)
        1. ISBN search — Browse API (condition-filtered)
        1.5. MPN/Model search — Browse API (condition-filtered)
        2. Keyword search — Browse API (condition-filtered)
        2.5. Research market price (AI web research)
        3. Gemini + Google Search grounding
        4. AI vision estimate (weakest signal)
        5. Fail loudly (returns None)
        """
        research_link = self.generate_ebay_search_link(title)

        # --- STRATEGY 1: ISBN SEARCH (Gold Standard for Books) ---
        if isbn:
            logger.info(f"[SEARCH] ISBN search: {isbn}...")
            sold_items = self.search_sold_listings(isbn, category_id, limit=15, condition=condition)
            if sold_items:
                sold_items = self.filter_comps(sold_items, reference_title=title)
                price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
                logger.info(f"   [PRICE] ISBN price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                return {
                    "suggested_price": price_data["suggested_price"],
                    "comps": sold_items[:5],
                    "reasoning": f"ISBN Match: {price_data['reasoning']}",
                    "projected_profit": price_data.get("projected_profit"),
                    "source": "market_data_isbn",
                    "research_link": self.generate_ebay_search_link(isbn)
                }
            logger.info("   [WARN] No listings found for ISBN, falling back to title...")

        # --- STRATEGY 1.5: MPN/MODEL SEARCH ---
        id_query_tried = None
        if identification:
            mpn = identification.get('mpn', '')
            brand = identification.get('brand', '')
            model = identification.get('model', '')

            id_parts = [p for p in [brand, mpn or model] if p]
            if id_parts and len(" ".join(id_parts)) >= 5:
                id_query = " ".join(id_parts)
                id_query_tried = id_query

                logger.info(f"[SEARCH] Identifier search: {id_query}...")
                sold_items = self.search_sold_listings(id_query, category_id, limit=15, condition=condition)
                if sold_items:
                    sold_items = self.filter_comps(sold_items, reference_title=title)
                    price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
                    logger.info(f"   [PRICE] ID price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                    return {
                        "suggested_price": price_data["suggested_price"],
                        "comps": sold_items[:5],
                        "reasoning": f"ID Match ({id_query}): {price_data['reasoning']}",
                        "projected_profit": price_data.get("projected_profit"),
                        "source": "market_data_id",
                        "research_link": self.generate_ebay_search_link(id_query)
                    }
                logger.info("   [WARN] No listings found for identifiers, trying alt part numbers...")

                # --- STRATEGY 1.5b: ALTERNATIVE PART NUMBERS ---
                alt_pns = identification.get('oem_part_numbers', []) or []
                if not alt_pns:
                    alt_pns = identification.get('alternative_part_numbers', []) or []
                for alt_pn in alt_pns[:3]:  # Try up to 3 alternatives
                    if not alt_pn:
                        continue
                    search_query = f"{brand} {alt_pn}" if brand else str(alt_pn)
                    logger.info(f"[SEARCH] Alt part number: {search_query}...")
                    sold_items = self.search_sold_listings(search_query, category_id, limit=10, condition=condition)
                    if sold_items:
                        sold_items = self.filter_comps(sold_items, reference_title=title)
                        price_data = self.calculate_suggested_price(
                            sold_items, condition, acquisition_cost, shipping_cost,
                            availability=availability
                        )
                        logger.info(f"   [PRICE] Alt PN price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                        return {
                            "suggested_price": price_data["suggested_price"],
                            "comps": sold_items[:5],
                            "reasoning": f"Alt PN Match ({alt_pn}): {price_data['reasoning']}",
                            "projected_profit": price_data.get("projected_profit"),
                            "source": "market_data_alt_pn",
                            "research_link": research_link
                        }

                logger.info("   [WARN] No alt part number results, falling back to title...")

        # --- STRATEGY 2: KEYWORD SEARCH ---
        search_query = self._build_keyword_query(title, identification)

        # Avoid re-searching the same query we already tried in Strategy 1.5
        if id_query_tried and search_query == id_query_tried:
            search_query = " ".join(title.split()[:8])  # Force title fallback

        logger.info(f"[SEARCH] Keyword search: {search_query[:50]}...")
        sold_items = self.search_sold_listings(search_query, category_id, limit=15, condition=condition)
        if sold_items:
            sold_items = self.filter_comps(sold_items, reference_title=title)
            price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
            logger.info(f"   [PRICE] Keyword price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
            return {
                "suggested_price": price_data["suggested_price"],
                "comps": sold_items[:5],
                "reasoning": price_data["reasoning"],
                "projected_profit": price_data.get("projected_profit"),
                "source": "market_data_keyword",
                "research_link": research_link
            }

        # --- STRATEGY 2.5: PHASE 2 RESEARCH MARKET PRICE ---
        if research_market_price and research_market_price.get('mid'):
            try:
                mid = float(research_market_price['mid'])
                adjusted = round(mid, 2)
                if shipping_cost > 0:
                    adjusted = round(adjusted + shipping_cost, 2)
                adjusted = self._smart_round_99(adjusted)
                adjusted = self._sanitize_price(adjusted)
                low = research_market_price.get('low', '?')
                high = research_market_price.get('high', '?')
                logger.info(f"   [PRICE] Research price: ${adjusted:.2f} (from Phase 2 web research ${low}-${high} range)")
                return {
                    "suggested_price": adjusted,
                    "comps": [],
                    "reasoning": f"Phase 2 web research: ${low}-${high} range ({condition})",
                    "source": "research_market_price",
                    "research_link": research_link
                }
            except (ValueError, TypeError) as e:
                logger.warning(f"   [WARN] Research market price unusable: {e}")

        # --- STRATEGY 3: GEMINI GROUNDING ---
        logger.info(f"[SEARCH] Performing AI Market Research (Gemini Grounding)...")
        grounded_result = self.get_ai_price_estimate(title, condition)
        if grounded_result:
            ai_price = grounded_result['price']
            ai_reasoning = grounded_result.get('reasoning', "Researched via Gemini")
            if shipping_cost > 0:
                ai_price = round(ai_price + shipping_cost, 2)
                ai_reasoning += f" + ${shipping_cost:.2f} free shipping buffer"
            ai_price = self._smart_round_99(ai_price)
            ai_price = self._sanitize_price(ai_price)
            logger.info(f"   [WEB] AI Research Price: ${ai_price:.2f}")
            return {
                "suggested_price": ai_price,
                "comps": [],
                "reasoning": ai_reasoning,
                "source": "ai_grounded_research",
                "research_link": research_link
            }

        # --- STRATEGY 4: AI VISION ESTIMATE ---
        if ai_suggested_price:
            fallback_price = float(ai_suggested_price)
            fallback_reasoning = "Based on logical inference from visual analysis (No market data found)"
            if shipping_cost > 0:
                fallback_price = round(fallback_price + shipping_cost, 2)
                fallback_reasoning += f" + ${shipping_cost:.2f} free shipping buffer"
            fallback_price = self._smart_round_99(fallback_price)
            fallback_price = self._sanitize_price(fallback_price)
            logger.info(f"   [INFO] Using AI image estimate: ${fallback_price}")
            return {
                "suggested_price": fallback_price,
                "comps": [],
                "reasoning": fallback_reasoning,
                "source": "ai_estimate",
                "research_link": research_link
            }

        # --- STRATEGY 5: FAIL LOUDLY ---
        logger.warning("   [FAIL] Price discovery failed. Manual pricing required.")
        return {
            "suggested_price": None,
            "comps": [],
            "reasoning": "Could not determine price. Manual input required.",
            "source": "failed_requires_manual",
            "research_link": research_link,
            "error": "Price discovery failed"
        }


# Test the pricing engine
if __name__ == "__main__":
    logger.info("Testing Pricing Engine...\n")
    
    engine = PricingEngine()
    
    if not engine.app_id:
        logger.warning("[WARN] EBAY_APP_ID not configured - using AI fallback only")
    
    # Test with a known item
    test_title = "NTTAT CLETOP REEL TYPE A Optical Fiber Connector Cleaner"
    test_condition = "Used - Good"
    test_ai_price = "49.99"
    
    result = engine.get_price_with_comps(test_title, test_condition, ai_suggested_price=test_ai_price)
    
    logger.info(f"\n[STATS] Results for: {test_title[:50]}...")
    logger.info(f"   Suggested Price: ${result['suggested_price']}" if result['suggested_price'] else "   No price suggestion")
    logger.info(f"   Source: {result['source']}")
    logger.info(f"   Reasoning: {result['reasoning']}")
    logger.info(f"   [LINK] Research: {result['research_link']}")
    
    if result['comps']:
        logger.info(f"\n   [COMPS] Recent Sales ({len(result['comps'])} shown):")
        for comp in result['comps']:
            logger.info(f"      ${comp['price']:.2f} - {comp['condition']} - {comp['end_date']}")
