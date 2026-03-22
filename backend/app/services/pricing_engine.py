"""
Pricing Engine for eBay Draft Commander
Uses eBay Finding API to get sold listings and calculate market-based prices
"""
import os
import json
import re
import statistics
import requests
from typing import List, Dict, Optional, Union, Any
from urllib.parse import quote
from backend.app.core.constants import AI_PRICING_MODEL
from backend.app.core.logger import get_logger
from backend.app.core.rate_limiter import limiter

logger = get_logger('pricing_engine')


class PricingEngine:
    """Calculates suggested prices based on recent eBay sales.

    Pricing cascade (in priority order):
    0. User override (manual price)
    1. ISBN search — Finding API (sold) -> Browse API (active)
    1.5. MPN/Model search — Finding API (sold) -> Browse API (active)
    2. Keyword search — Finding API (sold) -> Browse API (active)
    3. Gemini + Google Search grounding (AI web research)
    4. AI vision estimate (suggested_price from image analysis — weakest signal)
    5. Fail loudly (returns None, requires manual pricing)

    TODO (Future): Comp Image Comparison
    - Finding API returns sold data; fetch thumbnail images from results
    - Use Gemini multimodal to compare our product photos against comp photos
    - Score visual similarity to filter out non-matching comps
    - Weight prices by visual similarity for more accurate estimates
    - This would help with items where title search returns noisy results
    """
    
    # Finding API endpoint
    FINDING_API_URL = "https://svcs.ebay.com/services/search/FindingService/v1"
    
    # Condition multipliers (relative to median of "all conditions")
    CONDITION_MULTIPLIERS = {
        "New": 1.0,
        "New - Open Box": 0.90,
        "Used - Like New": 0.85,
        "Used - Good": 0.75,
        "Used - Acceptable": 0.60,
        "For Parts": 0.40,
        "For Parts or Not Working": 0.40,
        "New Old Stock": 0.95,  # NOS commands higher prices
        "New other (see details)": 0.90,
    }
    
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
        if price <= 10:
            return price
        import math
        base = math.floor(price)
        cents = price - base
        if cents >= 0.80:
            return base + 0.99
        return base - 0.01

    def _resolve_condition_multiplier(self, condition_str: str) -> Optional[float]:
        """Resolve a condition string from comps to a multiplier value.

        Handles various formats: display names ("Used - Good"), eBay API enums
        ("USED_GOOD"), and partial matches ("Like New").
        Returns None if condition is unrecognizable.
        """
        if not condition_str:
            return None

        # Direct match against our table
        if condition_str in self.CONDITION_MULTIPLIERS:
            return self.CONDITION_MULTIPLIERS[condition_str]

        # Try enum-to-display conversion
        from backend.app.core.constants import CONDITION_ENUM_TO_DISPLAY
        if condition_str in CONDITION_ENUM_TO_DISPLAY:
            display = CONDITION_ENUM_TO_DISPLAY[condition_str]
            return self.CONDITION_MULTIPLIERS.get(display)

        # Fuzzy matching on lowercase
        cond_lower = condition_str.lower()
        if "new" in cond_lower and "open" in cond_lower:
            return self.CONDITION_MULTIPLIERS["New - Open Box"]
        if "like new" in cond_lower:
            return self.CONDITION_MULTIPLIERS["Used - Like New"]
        if "good" in cond_lower:
            return self.CONDITION_MULTIPLIERS["Used - Good"]
        if "acceptable" in cond_lower:
            return self.CONDITION_MULTIPLIERS["Used - Acceptable"]
        if "parts" in cond_lower:
            return self.CONDITION_MULTIPLIERS["For Parts"]
        if "new" in cond_lower:
            return self.CONDITION_MULTIPLIERS["New"]

        return None

    def search_sold_listings(self, keywords: str, category_id: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Search for recently sold items matching the keywords.
        
        Args:
            keywords: Search query (e.g., "NTTAT CLETOP")
            category_id: Optional eBay category ID to narrow search
            limit: Max number of results (1-100)
        
        Returns:
            List of dicts with: title, price, condition, end_date, url
        """
        if not self.app_id:
            return []
        
        # Use eBayResearcher (Browse API) instead of legacy Finding API
        try:
            from backend.app.services.ebay.researcher import eBayResearcher
            researcher = eBayResearcher(use_api=True, use_ai=False) # AI fallback handled by caller if needed
            
            # The researcher returns {'items': [SoldItem...], ...}
            # We need to adapt it to the dict format expected by this class
            results = researcher.search_sold(keywords, limit=limit)
            
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
    
    def search_finding_api(self, keywords: str, category_id: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Search eBay Finding API for ACTUALLY SOLD items (last 90 days).

        Unlike Browse API (active listings / asking prices), Finding API
        findCompletedItems returns real transaction data -- what buyers paid.

        Args:
            keywords: Search query
            category_id: Optional eBay category ID
            limit: Max results (1-100)

        Returns:
            List of dicts with: title, price, condition, end_date, url
        """
        if not self.app_id:
            return []

        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.13.0",
            "SECURITY-APPNAME": self.app_id,
            "RESPONSE-DATA-FORMAT": "XML",
            "REST-PAYLOAD": "",
            "keywords": keywords,
            "paginationInput.entriesPerPage": str(min(limit, 100)),
            "itemFilter(0).name": "SoldItemsOnly",
            "itemFilter(0).value": "true",
            "itemFilter(1).name": "Currency",
            "itemFilter(1).value": "USD",
            "sortOrder": "EndTimeNewest",
        }

        if category_id:
            params["categoryId"] = category_id

        try:
            import xml.etree.ElementTree as ET

            limiter.wait_if_needed('ebay')
            response = requests.get(self.FINDING_API_URL, params=params, timeout=15)

            if response.status_code != 200:
                logger.warning(f"Finding API HTTP {response.status_code}")
                return []

            ns = {"ns": "https://svcs.ebay.com/services/search/FindingService/v1"}
            root = ET.fromstring(response.text)

            ack = root.findtext("ns:ack", default="Failure", namespaces=ns)
            if ack != "Success":
                error_msg = root.findtext(".//ns:errorMessage/ns:error/ns:message", default="Unknown", namespaces=ns)
                logger.warning(f"Finding API error: {error_msg}")
                return []

            sold_items = []
            for item_el in root.findall(".//ns:searchResult/ns:item", namespaces=ns):
                try:
                    title = item_el.findtext("ns:title", default="", namespaces=ns)

                    selling_state = item_el.findtext(
                        "ns:sellingStatus/ns:sellingState", default="", namespaces=ns
                    )
                    if selling_state != "EndedWithSales":
                        continue

                    price_str = item_el.findtext(
                        "ns:sellingStatus/ns:currentPrice", default="0", namespaces=ns
                    )
                    price = float(price_str)
                    if price <= 0:
                        continue

                    condition = item_el.findtext(
                        "ns:condition/ns:conditionDisplayName", default="Used", namespaces=ns
                    )
                    end_date = item_el.findtext(
                        "ns:listingInfo/ns:endTime", default="", namespaces=ns
                    )
                    url = item_el.findtext("ns:viewItemURL", default="", namespaces=ns)

                    sold_items.append({
                        "title": title,
                        "price": price,
                        "currency": "USD",
                        "condition": condition,
                        "end_date": end_date[:10] if end_date else "",
                        "url": url,
                    })
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Skipping Finding API item: {e}")
                    continue

            logger.info(f"Finding API returned {len(sold_items)} sold items for: {keywords[:50]}")
            return sold_items

        except Exception as e:
            logger.warning(f"Finding API request failed: {e}")
            return []

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
            idx = int(len(sorted_prices) * 0.75)
            base_price = sorted_prices[min(idx, len(sorted_prices) - 1)]
            reasoning_prefix = "75th pctl (rare)"
        else:
            base_price = median_price
            reasoning_prefix = "Median"

        # Get condition multiplier — resolve enum keys to display format
        from backend.app.core.constants import CONDITION_ENUM_TO_DISPLAY
        cond_key = our_condition
        # If it's an enum key (e.g. USED_EXCELLENT), convert to display format
        if cond_key in CONDITION_ENUM_TO_DISPLAY:
            cond_key = CONDITION_ENUM_TO_DISPLAY[cond_key]
        # Fuzzy match for NOS
        if "new old stock" in cond_key.lower() or "nos" in cond_key.lower():
            cond_key = "New Old Stock"

        our_multiplier = self.CONDITION_MULTIPLIERS.get(cond_key, 0.75)

        # --- Condition-Aware Multiplier ---
        # Comps come in mixed conditions. If most comps are already similar to
        # our condition, the median already reflects our condition's price level
        # and applying the full multiplier would double-discount.
        # Solution: estimate the "average condition level" of comps and scale
        # our multiplier relative to that baseline.
        comp_multipliers = []
        for item in sold_items:
            comp_cond = item.get("condition", "")
            # Try to match comp condition to our multiplier table
            comp_mult = self._resolve_condition_multiplier(comp_cond)
            if comp_mult is not None:
                comp_multipliers.append(comp_mult)

        if comp_multipliers:
            avg_comp_multiplier = statistics.mean(comp_multipliers)
            # Relative multiplier: our condition vs the average comp condition
            # If comps are mostly "Used - Good" (0.75) and we're also "Used - Good" (0.75),
            # relative multiplier = 0.75 / 0.75 = 1.0 (no adjustment needed)
            # If comps are mixed (avg ~0.85) and we're "Used - Good" (0.75),
            # relative multiplier = 0.75 / 0.85 = 0.88 (modest discount)
            multiplier = our_multiplier / avg_comp_multiplier if avg_comp_multiplier > 0 else our_multiplier
            # Clamp to reasonable range (0.4x to 1.3x) to avoid extreme adjustments
            multiplier = max(0.40, min(1.30, multiplier))
        else:
            # No condition data on comps — use raw multiplier as before
            multiplier = our_multiplier

        # Calculate suggested price
        suggested_price = round(base_price * multiplier, 2)

        # --- Free Shipping Buffer ---
        # When offering free shipping, bake the estimated shipping cost into the price
        shipping_buffered = False
        if shipping_cost > 0:
            suggested_price = round(suggested_price + shipping_cost, 2)
            shipping_buffered = True

        # --- Margin Protection ---
        # Estimated eBay Fees: ~13.25% + $0.30
        est_fees = (suggested_price * 0.1325) + 0.30
        projected_profit = suggested_price - est_fees - acquisition_cost - shipping_cost
        
        min_margin = 10.00 # Minimum desired profit per item
        margin_boost = False
        
        if acquisition_cost > 0 and projected_profit < min_margin:
            # Price is too low for target margin, calculate target price
            # Target = (Cost + MinMargin + 0.30) / (1 - 0.1325)
            target_price = (acquisition_cost + min_margin + 0.30) / (1 - 0.1325)
            suggested_price = round(target_price, 2)
            margin_boost = True
            
        # Smart pricing: round to nearest .99 without aggressive inflation
        suggested_price = self._smart_round_99(suggested_price)

        reasoning = f"{reasoning_prefix} of {len(prices)} sales (${base_price:.2f}) x {multiplier:.0%} condition adj."
        if shipping_buffered:
            reasoning += f" + ${shipping_cost:.2f} shipping"
        if margin_boost:
            reasoning += f" (Boosted for ${min_margin} min margin)"
            
        return {
            "suggested_price": suggested_price,
            "comp_count": len(prices),
            "median_price": round(median_price, 2),
            "multiplier": multiplier,
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
                "original_msrp_estimate": "$XXX.XX",
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
        1. ISBN search -- Finding API (sold) -> Browse API (active)
        1.5. MPN/Model search -- Finding API (sold) -> Browse API (active)
        2. Keyword search -- Finding API (sold) -> Browse API (active)
        3. Gemini + Google Search grounding
        4. AI vision estimate (weakest signal)
        5. Fail loudly (returns None)
        """
        research_link = self.generate_ebay_search_link(title)

        # --- STRATEGY 1: ISBN SEARCH (Gold Standard for Books) ---
        if isbn:
            # Try Finding API (sold data) first
            logger.info(f"[SEARCH] ISBN sold search: {isbn}...")
            sold_items = self.search_finding_api(isbn, category_id, limit=15)
            if sold_items:
                price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
                logger.info(f"   [PRICE] Sold price (ISBN): ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                return {
                    "suggested_price": price_data["suggested_price"],
                    "comps": sold_items[:5],
                    "reasoning": f"ISBN Sold Match: {price_data['reasoning']}",
                    "projected_profit": price_data.get("projected_profit"),
                    "source": "market_data_isbn_sold",
                    "research_link": self.generate_ebay_search_link(isbn)
                }

            # Fallback: Browse API (active listings)
            logger.info(f"   [WARN] No sold data for ISBN, trying active listings...")
            sold_items = self.search_sold_listings(isbn, category_id, limit=15)
            if sold_items:
                price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
                logger.info(f"   [PRICE] Active price (ISBN): ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                return {
                    "suggested_price": price_data["suggested_price"],
                    "comps": sold_items[:5],
                    "reasoning": f"ISBN Match: {price_data['reasoning']}",
                    "projected_profit": price_data.get("projected_profit"),
                    "source": "market_data_isbn",
                    "research_link": self.generate_ebay_search_link(isbn)
                }
            logger.info("   [WARN] No sales found for ISBN, falling back to title...")

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

                # Try Finding API (sold data) first
                logger.info(f"[SEARCH] Identifier sold search: {id_query}...")
                sold_items = self.search_finding_api(id_query, category_id, limit=15)
                if sold_items:
                    price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
                    logger.info(f"   [PRICE] Sold price (ID): ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                    return {
                        "suggested_price": price_data["suggested_price"],
                        "comps": sold_items[:5],
                        "reasoning": f"ID Sold Match ({id_query}): {price_data['reasoning']}",
                        "projected_profit": price_data.get("projected_profit"),
                        "source": "market_data_id_sold",
                        "research_link": self.generate_ebay_search_link(id_query)
                    }

                # Fallback: Browse API (active listings)
                logger.info(f"   [WARN] No sold data for identifiers, trying active listings...")
                sold_items = self.search_sold_listings(id_query, category_id, limit=15)
                if sold_items:
                    price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
                    logger.info(f"   [PRICE] Active price (ID): ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                    return {
                        "suggested_price": price_data["suggested_price"],
                        "comps": sold_items[:5],
                        "reasoning": f"ID Match ({id_query}): {price_data['reasoning']}",
                        "projected_profit": price_data.get("projected_profit"),
                        "source": "market_data_id",
                        "research_link": self.generate_ebay_search_link(id_query)
                    }
                logger.info("   [WARN] No sales found for identifiers, falling back to title...")

        # --- STRATEGY 2: KEYWORD SEARCH ---
        search_query = self._build_keyword_query(title, identification)

        # Avoid re-searching the same query we already tried in Strategy 1.5
        if id_query_tried and search_query == id_query_tried:
            search_query = " ".join(title.split()[:8])  # Force title fallback

        # Try Finding API (sold data) first
        logger.info(f"[SEARCH] Keyword sold search: {search_query[:50]}...")
        sold_items = self.search_finding_api(search_query, category_id, limit=15)
        if sold_items:
            price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
            logger.info(f"   [PRICE] Sold price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
            return {
                "suggested_price": price_data["suggested_price"],
                "comps": sold_items[:5],
                "reasoning": f"Sold: {price_data['reasoning']}",
                "projected_profit": price_data.get("projected_profit"),
                "source": "market_data_sold",
                "research_link": research_link
            }

        # Fallback: Browse API (active listings)
        logger.info(f"   [WARN] No sold data, trying active listings: {search_query[:50]}...")
        sold_items = self.search_sold_listings(search_query, category_id, limit=15)
        if sold_items:
            price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
            logger.info(f"   [PRICE] Active price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
            return {
                "suggested_price": price_data["suggested_price"],
                "comps": sold_items[:5],
                "reasoning": price_data["reasoning"],
                "projected_profit": price_data.get("projected_profit"),
                "source": "market_data",
                "research_link": research_link
            }

        # --- STRATEGY 2.5: PHASE 2 RESEARCH MARKET PRICE ---
        if research_market_price and research_market_price.get('mid'):
            try:
                mid = float(research_market_price['mid'])
                # Apply condition multiplier (same logic as calculate_suggested_price)
                multiplier = self._resolve_condition_multiplier(condition) or 0.75
                adjusted = round(mid * multiplier, 2)
                if shipping_cost > 0:
                    adjusted = round(adjusted + shipping_cost, 2)
                adjusted = self._smart_round_99(adjusted)
                low = research_market_price.get('low', '?')
                high = research_market_price.get('high', '?')
                logger.info(f"   [PRICE] Research price: ${adjusted:.2f} (from Phase 2 web research ${low}-${high} range)")
                return {
                    "suggested_price": adjusted,
                    "comps": [],
                    "reasoning": f"Phase 2 web research: ${low}-${high} range, condition adjusted ({condition})",
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
