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
    ACTIVE_TO_SOLD_FACTOR,
    PRICE_AGREEMENT_RATIO,
)
from backend.app.core.logger import get_logger
from backend.app.core.prompts import build_seller_note_block
from backend.app.services.sourcing import assess_confidence

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
                        "url": item['url'],
                        # Thumbnail for the "why this price" comp cards
                        "image_url": item.get('imageUrl', '')
                    })
            
            return sold_items

        except ImportError:
            logger.error("[FAIL] Could not import eBayResearcher")
            return []
        except Exception as e:
            logger.error(f"[FAIL] Pricing engine error (using Researcher): {e}")
            return []
    
    MIN_TITLE_SIMILARITY = 0.40  # Min distinctive-token overlap ratio (raised from 0.30)
    MIN_COMPS_AFTER_FILTER = 3   # Don't filter below this count

    # Generic descriptors with no product identity. Stripped from the REFERENCE
    # tokens before overlap so distinctive tokens (brand/model/type) dominate.
    _STOPWORDS = frozenset({
        'new', 'used', 'preowned', 'pre-owned', 'vintage', 'antique', 'rare',
        'genuine', 'authentic', 'original', 'oem', 'official', 'brand', 'lot',
        'with', 'without', 'for', 'the', 'and', 'a', 'an', 'of', 'in', 'to',
        'set', 'x', 'w', 'excellent', 'good', 'great', 'condition', 'working',
        'tested', 'works', 'free', 'shipping', 'fast', 'nice', 'clean',
    })

    # Accessory / parts / non-item signals. HIGH PRECISION: a token here is only
    # applied when the REFERENCE does NOT contain it (so a "Replacement Band"
    # listing still keeps 'band'/'replacement' comps).
    _NEGATIVE_TOKENS = frozenset({
        'accessory', 'accessories', 'replacement', 'repair', 'parts', 'part',
        'broken', 'cracked', 'damaged', 'defective', 'salvage', 'faulty',
        'manual', 'manuals', 'instruction', 'instructions', 'guide',
        'strap', 'band', 'bracket', 'mount', 'adapter', 'charger', 'cable',
        'battery', 'batteries', 'remote', 'faceplate', 'sticker', 'stickers',
        'decal', 'decals', 'poster', 'bulk', 'wholesale',
    })
    # Multi-word junk signals matched as substrings of the raw lowercased title.
    _NEGATIVE_PHRASES = (
        'for parts', 'not working', 'as-is', 'as is', 'does not work',
        "doesn't work", 'read description', 'box only', 'case only',
        'cover only', 'bag only', 'strap only', 'band only', 'manual only',
        'empty box', 'lot of',
    )

    # A model number: alphanumeric mix, length >= 4 (e.g. L35AF, SX230, CSD-ES227).
    _MODEL_RE = re.compile(r"^(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)[a-z0-9-]{4,}$")
    # Measurements that would otherwise look like model numbers (35mm, 256gb).
    _MEASUREMENT_RE = re.compile(
        r"^\d+(?:mm|cm|in|ft|oz|lbs?|ml|gb|tb|mah|hz|khz|mhz|ghz|v|w|k|p)$"
    )

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Lowercase word tokens; keeps hyphenated model numbers intact (csd-es227)."""
        return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", (text or "").lower())

    @staticmethod
    def _norm(text: str) -> str:
        """Collapse to bare alphanumerics for robust model-number containment."""
        return re.sub(r"[^a-z0-9]", "", (text or "").lower())

    @classmethod
    def _detect_model_number(cls, title: str) -> Optional[str]:
        """Return the most model-number-like token in the reference, or None.
        Longest qualifying token wins (favours 'l35af' over the '35mm' measurement)."""
        cands = [
            t for t in cls._tokenize(title)
            if cls._MODEL_RE.match(t) and not cls._MEASUREMENT_RE.match(t)
        ]
        return max(cands, key=len) if cands else None

    @classmethod
    def _is_junk_comp(cls, title: str, neg_tokens: frozenset, neg_phrases: tuple) -> bool:
        low = (title or "").lower()
        if any(p in low for p in neg_phrases):
            return True
        return bool(set(cls._tokenize(title)) & neg_tokens)

    @classmethod
    def _reject_price_outliers(cls, comps: List[Dict]) -> List[Dict]:
        """Tukey/IQR fences on price. Runs only on >=5 priced comps and never
        drops below the floor. Applied AFTER junk removal so the quartiles reflect
        the real product, not accessory contamination."""
        prices = sorted(c["price"] for c in comps if c.get("price", 0) > 0)
        if len(prices) < 5:
            return comps
        q1, _, q3 = statistics.quantiles(prices, n=4, method="exclusive")
        iqr = q3 - q1
        if iqr <= 0:
            return comps
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        kept = [c for c in comps if lower <= c.get("price", 0) <= upper]
        return kept if len(kept) >= cls.MIN_COMPS_AFTER_FILTER else comps

    def filter_comps(self, comps: List[Dict], reference_title: str,
                     exact_id: bool = False, with_meta: bool = False) -> Any:
        """Reduce comps to true same-product matches before pricing.

        Keyword pipeline (each stage keeps MIN_COMPS_AFTER_FILTER as a floor):
          1. Junk removal   - drop accessory/parts/for-parts/manual/lot comps,
                              but never on a token the reference itself uses.
          2. Positive match - stopword-stripped title overlap; if the reference
                              carries a model number (e.g. L35AF) gate to comps
                              that contain it.
          3. Outlier reject - IQR/Tukey fences on price, AFTER junk removal.

        exact_id=True (ISBN/UPC) skips stages 1-2 (product identity is already
        guaranteed by the identifier match) and only runs stage 3.

        with_meta=True returns (comps, meta) where meta describes HOW the comps
        matched so callers can grade trust:
          match_quality: 'model_gated' | 'similar' | 'floor_fallback'
                         | 'exact_id' | 'small_set'
          junk_removed:  count of accessory/parts comps dropped in Phase 1
        """
        def _out(lst, quality, junk_removed=0):
            if with_meta:
                return lst, {"match_quality": quality, "junk_removed": junk_removed}
            return lst

        if len(comps) <= self.MIN_COMPS_AFTER_FILTER:
            return _out(comps, "small_set")

        if exact_id:
            return _out(self._reject_price_outliers(list(comps)), "exact_id")

        ref_low = (reference_title or "").lower()
        ref_tokens = set(self._tokenize(reference_title))
        ref_content = ref_tokens - self._STOPWORDS
        model_key = self._norm(self._detect_model_number(reference_title) or "")

        # Reference-guard: never filter on junk terms the reference itself uses.
        active_tokens = self._NEGATIVE_TOKENS - ref_tokens
        active_phrases = tuple(p for p in self._NEGATIVE_PHRASES if p not in ref_low)

        # --- Phase 1: junk / accessory removal ---
        kept = [c for c in comps
                if not self._is_junk_comp(c.get("title", ""), active_tokens, active_phrases)]
        junk_removed = len(comps) - len(kept)
        if len(kept) < self.MIN_COMPS_AFTER_FILTER:
            kept = list(comps)  # everything looked like junk — don't strand ourselves
            junk_removed = 0

        # --- Phase 2: positive similarity + model-number gate ---
        scored = []  # (overlap, has_model, comp)
        for c in kept:
            title = c.get("title", "")
            comp_tokens = set(self._tokenize(title))
            overlap = (len(ref_content & comp_tokens) / len(ref_content)) if ref_content else 0.0
            has_model = bool(model_key) and model_key in self._norm(title)
            scored.append((overlap, has_model, c))

        gated = [t for t in scored if t[1]] if model_key else []
        if len(gated) >= self.MIN_COMPS_AFTER_FILTER:
            candidates = gated                       # the model # IS the match
            quality = "model_gated"
        else:
            similar = [t for t in scored if t[0] >= self.MIN_TITLE_SIMILARITY]
            if len(similar) >= self.MIN_COMPS_AFTER_FILTER:
                candidates = similar
                quality = "similar"
            else:
                scored.sort(key=lambda t: (t[1], t[0]), reverse=True)
                candidates = scored[:self.MIN_COMPS_AFTER_FILTER]
                quality = "floor_fallback"

        # Best matches first (model hits, then overlap) for downstream comps[:N] use.
        candidates.sort(key=lambda t: (t[1], t[0]), reverse=True)
        title_filtered = [c for _, _, c in candidates]

        # --- Phase 3: price-outlier rejection (post-junk) ---
        return _out(self._reject_price_outliers(title_filtered), quality, junk_removed)

    def _comps_confidence(self, sold_items: List[Dict], price_data: Dict,
                          id_type: str, match_quality: Optional[str] = None) -> tuple:
        """(confidence, reason) for a comp-backed price."""
        prices = [c["price"] for c in sold_items if c.get("price", 0) > 0]
        return assess_confidence(price_data.get('comp_count', 0), prices, id_type,
                                 match_quality=match_quality)

    def _ai_cross_check(self, title: str, condition: str, identification: Optional[Dict],
                        research_market_price: Optional[Dict], shipping_cost: float,
                        seller_note: str = "") -> tuple:
        """Second opinion for weak keyword comps: Phase-2 research mid if already
        fetched (free), else one Gemini grounding call (skipped on FAST_MODE).
        Returns (final_list_price | None, origin_label | None) — final price has
        the shipping buffer + smart rounding applied so it compares like-for-like
        with a comp-based suggested_price."""
        raw = None
        origin = None
        if research_market_price and research_market_price.get('mid'):
            try:
                raw = float(research_market_price['mid'])
                origin = 'web research'
            except (TypeError, ValueError):
                raw = None
        if raw is None:
            fast_mode = os.environ.get('FAST_MODE', 'false').lower() == 'true'
            if not fast_mode:
                grounded = self.get_ai_price_estimate(
                    title, condition, identification=identification, seller_note=seller_note)
                if grounded and grounded.get('price'):
                    try:
                        raw = float(grounded['price'])
                        origin = 'AI research'
                    except (TypeError, ValueError):
                        raw = None
        if not raw or raw <= 0:
            return None, None
        final = round(raw + shipping_cost, 2) if shipping_cost > 0 else raw
        final = self._sanitize_price(self._smart_round_99(final))
        return final, origin

    # Ordered: multi-word grades first so 'very good' never matches 'good',
    # 'like new' never matches 'new'.
    _GRADE_KEYWORDS = [
        ('like new', 'like_new'),
        ('very good', 'very_good'),
        ('excellent', 'excellent'),
        ('acceptable', 'acceptable'),
        ('parts', 'parts'),
        ('good', 'good'),
        ('new', 'new'),
    ]

    @classmethod
    def _grade_of(cls, condition) -> Optional[str]:
        if not condition:
            return None
        text = str(condition).lower().replace('_', ' ')
        for keyword, grade in cls._GRADE_KEYWORDS:
            if keyword in text:
                return grade
        return None

    @classmethod
    def prefer_same_grade_comps(cls, sold_items: List[Dict], our_condition, min_count: int = 4) -> tuple:
        """eBay's Browse API condition filter only buckets NEW/USED, so 'USED'
        comps mix Excellent with Acceptable grades. When enough comps share our
        exact grade, price from those alone. Returns (subset, filtered)."""
        our_grade = cls._grade_of(our_condition)
        if not our_grade:
            return sold_items, False
        matches = [item for item in sold_items if cls._grade_of(item.get('condition')) == our_grade]
        if len(matches) >= min_count:
            return matches, True
        return sold_items, False

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
        
        sold_items, grade_filtered = self.prefer_same_grade_comps(sold_items, our_condition)

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

        # Comps come from ACTIVE listings (asking prices), which run higher than
        # actual sold prices. Discount base_price toward estimated sold value.
        raw_market_price = base_price
        base_price = base_price * ACTIVE_TO_SOLD_FACTOR

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

        reasoning = f"{reasoning_prefix} of {len(prices)} listings (${raw_market_price:.2f} asking x{ACTIVE_TO_SOLD_FACTOR:g} = ${base_price:.2f})"
        if grade_filtered:
            reasoning += " [same-grade comps]"
        if shipping_buffered:
            reasoning += f" + ${shipping_cost:.2f} shipping"
        if margin_boost:
            reasoning += f" (Boosted for ${min_margin} min margin)"

        return {
            "suggested_price": suggested_price,
            "comp_count": len(prices),
            "median_price": round(median_price, 2),
            # Raw asking-price spread of the comps that priced this item —
            # drives the range bar in the frontend price explainer.
            "price_range": [round(min(prices), 2), round(max(prices), 2)],
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
    
    def get_ai_price_estimate(self, title: str, condition: str, identification: Optional[Dict] = None, seller_note: str = "") -> Optional[Dict[str, Union[float, str]]]:
        """Estimate price using Gemini with Google Search grounding.

        identification (brand/model/mpn/part numbers) is woven into the prompt so the model
        can search for the EXACT item — the single biggest factor for obscure/industrial parts.
        """
        if not self.ai_client:
            return None

        try:
            from google.genai import types

            # IMPORTANT: Search Grounding + JSON Mode often conflicts (INVALID_ARGUMENT).
            # We must use TEXT mode and parse the JSON out manually.

            # Identifier block — part numbers/MPN are the best way to find an obscure item.
            ident = identification or {}
            _id_lines = []
            for _label, _key in (("Brand", "brand"), ("Model", "model"), ("MPN", "mpn")):
                _v = ident.get(_key)
                if _v:
                    _id_lines.append(f"{_label}: {_v}")
            _parts = [str(p) for p in ((ident.get('oem_part_numbers') or []) + (ident.get('alternative_part_numbers') or [])) if p]
            if _parts:
                _id_lines.append("Part numbers (search these EXACT numbers): " + ", ".join(_parts[:6]))
            identifier_block = "\n            ".join(_id_lines) if _id_lines else "(no specific identifiers extracted)"
            seller_note_block = build_seller_note_block(seller_note)

            prompt = f"""You are a High-End Industrial Appraiser and eBay Pricing Strategist.
            The user has an item that may be rare, industrial, or undervalued.
            Do NOT default to a low price just because direct sales data is scarce.
            NEVER return 0 or a token price: if you cannot find the exact item, estimate from the
            closest comparable or from its category/MSRP and explain. Always justify a positive price.
            IMPORTANT: Return the BASE market value only. Do NOT include ANY shipping
            costs or shipping buffers. Shipping is handled separately by the caller.

            Item Title: {title}
            Condition: {condition}
            Identifiers:
            {identifier_block}
            {seller_note_block}

            Use the EXACT part numbers / MPN above in your web searches first — they are the single
            best way to find this specific item's market price.
            
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
            brand = (identification.get('brand') or '').strip()
            mpn = (identification.get('mpn') or '').strip()
            model = (identification.get('model') or '').strip()
            product_type = (identification.get('product_type') or '').strip()

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

    def get_price_with_comps(self, title: str, condition: str = "Used - Good", category_id: Optional[str] = None, ai_suggested_price: Optional[str] = None, acquisition_cost: float = 0.0, isbn: Optional[str] = None, shipping_cost: float = 0.0, identification: Optional[Dict] = None, research_market_price: Optional[Dict] = None, availability: Optional[str] = None, seller_note: str = "") -> Dict[str, Any]:
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
                sold_items = self.filter_comps(sold_items, reference_title=title, exact_id=True)
                price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
                confidence, confidence_reason = self._comps_confidence(
                    sold_items, price_data, 'isbn', match_quality='exact_id')
                logger.info(f"   [PRICE] ISBN price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                return {
                    "suggested_price": price_data["suggested_price"],
                    "comps": sold_items[:5],
                    "median_price": price_data.get("median_price"),
                    "comp_count": price_data.get("comp_count"),
                    "price_range": price_data.get("price_range"),
                    "reasoning": f"ISBN Match: {price_data['reasoning']}",
                    "projected_profit": price_data.get("projected_profit"),
                    "source": "market_data_isbn",
                    "confidence": confidence,
                    "confidence_reason": confidence_reason,
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
                    confidence, confidence_reason = self._comps_confidence(
                        sold_items, price_data, 'mpn')
                    logger.info(f"   [PRICE] ID price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                    return {
                        "suggested_price": price_data["suggested_price"],
                        "comps": sold_items[:5],
                        "median_price": price_data.get("median_price"),
                        "comp_count": price_data.get("comp_count"),
                        "price_range": price_data.get("price_range"),
                        "reasoning": f"ID Match ({id_query}): {price_data['reasoning']}",
                        "projected_profit": price_data.get("projected_profit"),
                        "source": "market_data_id",
                        "confidence": confidence,
                        "confidence_reason": confidence_reason,
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
                        confidence, confidence_reason = self._comps_confidence(
                            sold_items, price_data, 'mpn')
                        logger.info(f"   [PRICE] Alt PN price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                        return {
                            "suggested_price": price_data["suggested_price"],
                            "comps": sold_items[:5],
                            "median_price": price_data.get("median_price"),
                            "comp_count": price_data.get("comp_count"),
                            "price_range": price_data.get("price_range"),
                            "reasoning": f"Alt PN Match ({alt_pn}): {price_data['reasoning']}",
                            "projected_profit": price_data.get("projected_profit"),
                            "source": "market_data_alt_pn",
                            "confidence": confidence,
                            "confidence_reason": confidence_reason,
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
            sold_items, comp_meta = self.filter_comps(
                sold_items, reference_title=title, with_meta=True)
            price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost, shipping_cost, availability=availability)
            confidence, confidence_reason = self._comps_confidence(
                sold_items, price_data, 'keyword',
                match_quality=comp_meta.get('match_quality'))
            comp_final = price_data.get("suggested_price")

            # Keyword comps are the weakest identity match — junk (accessories,
            # parts, wrong variants) drags the median down and silently
            # under-prices. When the engine doesn't fully trust its own number,
            # get a second opinion and arbitrate instead of short-circuiting.
            if confidence != 'high' and comp_final:
                ai_final, ai_origin = self._ai_cross_check(
                    title, condition, identification, research_market_price,
                    shipping_cost, seller_note)
                if ai_final:
                    ratio = max(ai_final, comp_final) / max(min(ai_final, comp_final), 0.01)
                    if ratio <= PRICE_AGREEMENT_RATIO:
                        # Independent signal lands near the comps -> corroborated.
                        confidence = 'high' if confidence == 'medium' else 'medium'
                        confidence_reason += f"; corroborated by {ai_origin} (${ai_final:.2f})"
                        logger.info(f"   [OK] Comps corroborated by {ai_origin}: "
                                    f"${comp_final:.2f} vs ${ai_final:.2f}")
                    else:
                        # Wild disagreement -> comps are probably junk. Pre-fill
                        # the AI price and flag low confidence so the pipeline
                        # routes to review instead of listing at a junk price.
                        conflict_reason = (
                            f"comps say ${comp_final:.2f} ({price_data.get('comp_count', 0)} comps) "
                            f"but AI research says ${ai_final:.2f} — {ratio:.1f}x apart")
                        logger.warning(f"   [CONFLICT] {conflict_reason} -> review, AI price pre-filled")
                        return {
                            "suggested_price": ai_final,
                            "comp_price": comp_final,
                            "ai_price": ai_final,
                            "comps": sold_items[:5],
                            "median_price": price_data.get("median_price"),
                            "comp_count": price_data.get("comp_count"),
                            "price_range": price_data.get("price_range"),
                            "reasoning": f"Comp/AI conflict: {conflict_reason}",
                            "source": "market_ai_conflict",
                            "confidence": "low",
                            "confidence_reason": conflict_reason,
                            "research_link": research_link
                        }

            logger.info(f"   [PRICE] Keyword price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
            return {
                "suggested_price": price_data["suggested_price"],
                "comps": sold_items[:5],
                "median_price": price_data.get("median_price"),
                "comp_count": price_data.get("comp_count"),
                "price_range": price_data.get("price_range"),
                "reasoning": price_data["reasoning"],
                "projected_profit": price_data.get("projected_profit"),
                "source": "market_data_keyword",
                "confidence": confidence,
                "confidence_reason": confidence_reason,
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
                    "confidence": "medium",
                    "confidence_reason": "AI web research range (no market comps)",
                    "research_link": research_link
                }
            except (ValueError, TypeError) as e:
                logger.warning(f"   [WARN] Research market price unusable: {e}")

        # --- STRATEGY 3: GEMINI GROUNDING ---
        fast_mode = os.environ.get('FAST_MODE', 'false').lower() == 'true'
        if fast_mode:
            logger.info("[FAST] Skipping Gemini grounding (FAST_MODE=true)")
            grounded_result = None
        else:
            logger.info(f"[SEARCH] Performing AI Market Research (Gemini Grounding)...")
            grounded_result = self.get_ai_price_estimate(title, condition, identification=identification, seller_note=seller_note)
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
                "confidence": "medium",
                "confidence_reason": "AI research estimate (no market comps)",
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
                "confidence": "low",
                "confidence_reason": "AI vision estimate (no market data)",
                "research_link": research_link
            }

        # --- STRATEGY 5: FAIL LOUDLY ---
        logger.warning("   [FAIL] Price discovery failed. Manual pricing required.")
        return {
            "suggested_price": None,
            "comps": [],
            "reasoning": "Could not determine price. Manual input required.",
            "source": "failed_requires_manual",
            "confidence": "low",
            "confidence_reason": "No price signal from any source",
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
