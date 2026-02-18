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
from pathlib import Path
from urllib.parse import quote
from backend.app.core.logger import get_logger

logger = get_logger('pricing_engine')


class PricingEngine:
    """Calculates suggested prices based on recent eBay sales"""
    
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
        """Initialize with eBay App ID from .env"""
        env_path = Path(__file__).resolve().parents[3] / ".env"
        self.app_id = None
        
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('EBAY_APP_ID='):
                        self.app_id = line.split('=')[1].strip()
                        break
        
        if not self.app_id:
            logger.warning("⚠️ EBAY_APP_ID not found in .env - Pricing Intelligence disabled")
            
        # Initialize Gemini 3 for Search Grounding (from Roadmap Phase 6)
        self.google_api_key = None
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('GOOGLE_API_KEY='):
                        self.google_api_key = line.split('=')[1].strip()
                        break
        
        if not self.google_api_key:
            self.google_api_key = os.getenv('GOOGLE_API_KEY')
            
        self.ai_client = None
        if self.google_api_key:
            try:
                from google import genai
                self.ai_client = genai.Client(api_key=self.google_api_key)
                logger.info("✅ Pricing AI initialized (Gemini 3 + Search Grounding)")
            except Exception as e:
                logger.warning(f"⚠️ Could not initialize Pricing AI: {e}")
    
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
            logger.error("❌ Could not import eBayResearcher")
            return []
        except Exception as e:
            logger.error(f"❌ Pricing engine error (using Researcher): {e}")
            return []
    
    def calculate_suggested_price(self, sold_items: List[Dict], our_condition: str = "Used - Good", acquisition_cost: float = 0.0) -> Dict[str, Any]:
        """
        Calculate a suggested price based on sold items data.
        
        Uses median price (robust to outliers) with condition adjustment.
        Also performs margin protection check against acquisition cost.
        
        Args:
            sold_items: List of dicts from search_sold_listings()
            our_condition: The condition of our item
            acquisition_cost: Cost of goods sold (default 0.0)
        
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
        
        # Get condition multiplier
        # Fuzzy match for NOS
        cond_key = our_condition
        if "new old stock" in our_condition.lower() or "nos" in our_condition.lower():
            cond_key = "New Old Stock"
            
        multiplier = self.CONDITION_MULTIPLIERS.get(cond_key, 0.75)
        
        # Calculate suggested price
        suggested_price = round(median_price * multiplier, 2)
        
        # --- Margin Protection ---
        # Estimated eBay Fees: ~13.25% + $0.30
        est_fees = (suggested_price * 0.1325) + 0.30
        projected_profit = suggested_price - est_fees - acquisition_cost
        
        min_margin = 10.00 # Minimum desired profit per item
        margin_boost = False
        
        if acquisition_cost > 0 and projected_profit < min_margin:
            # Price is too low for target margin, calculate target price
            # Target = (Cost + MinMargin + 0.30) / (1 - 0.1325)
            target_price = (acquisition_cost + min_margin + 0.30) / (1 - 0.1325)
            suggested_price = round(target_price, 2)
            margin_boost = True
            
        # Smart pricing: round to .99 or .95
        if suggested_price > 10:
            suggested_price = round(suggested_price) - 0.01  # e.g., 45.00 -> 44.99
        
        reasoning = f"Median of {len(prices)} sales (${median_price:.2f}) × {multiplier:.0%} condition"
        if margin_boost:
            reasoning += f" (Boosted for ${min_margin} min margin)"
            
        return {
            "suggested_price": suggested_price,
            "comp_count": len(prices),
            "median_price": round(median_price, 2),
            "multiplier": multiplier,
            "reasoning": reasoning,
            "projected_profit": round(suggested_price - est_fees - acquisition_cost, 2)
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
        """Estimate price using Gemini 3 with Google Search grounding"""
        if not self.ai_client:
            return None
            
        try:
            from google.genai import types
            
            # IMPORTANT: Search Grounding + JSON Mode often conflicts (INVALID_ARGUMENT).
            # We must use TEXT mode and parse the JSON out manually.
            
            prompt = f"""You are a High-End Industrial Appraiser and eBay Pricing Strategist.
            The user has an item that may be rare, industrial, or undervalued. 
            Do NOT default to a low price just because direct sales data is scarce.
            
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
                model='gemini-3-flash-preview',
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
            logger.warning(f"   ⚠️ Gemini 3 Grounding failed: {e}")
            
            # FALLBACK: Try Standard Inference (No Tools) if Grounding crashes
            try:
                logger.info("   🔄 Retrying with robust logical inference (No Search Tools)...")
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
                    model='gemini-3-flash-preview',
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
                logger.error(f"   ❌ Standard Inference also failed: {e2}")

        return None

    def get_price_with_comps(self, title: str, condition: str = "Used - Good", category_id: Optional[str] = None, ai_suggested_price: Optional[str] = None, acquisition_cost: float = 0.0, isbn: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point: Get suggested price and comparable sales data.
        Falls back to AI suggestion if API fails.
        """
        # Generate research link for user
        research_link = self.generate_ebay_search_link(title)
        
        search_query = ""
        
        # --- STRATEGY 1: ISBN SEARCH (Gold Standard for Books) ---
        if isbn:
             logger.info(f"🔍 Searching sold listings by ISBN: {isbn}...")
             sold_items = self.search_sold_listings(isbn, category_id, limit=15)
             
             if sold_items:
                 price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost)
                 logger.info(f"   💰 Market price (ISBN): ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
                 
                 return {
                    "suggested_price": price_data["suggested_price"],
                    "comps": sold_items[:5],
                    "reasoning": f"ISBN Match: {price_data['reasoning']}",
                    "projected_profit": price_data.get("projected_profit"),
                    "source": "market_data_isbn",
                    "research_link": self.generate_ebay_search_link(isbn) # Override link
                }
             else:
                 logger.info("   ⚠️ No sales found for exact ISBN, falling back to title...")
        
        # --- STRATEGY 2: KEYWORD SEARCH ---
        # Clean up title for search (remove special chars, limit length)
        search_query = " ".join(title.split()[:8])  # First 8 words
        
        logger.info(f"🔍 Searching sold listings for: {search_query[:50]}...")
        
        sold_items = self.search_sold_listings(search_query, category_id, limit=15)
        
        if sold_items:
            price_data = self.calculate_suggested_price(sold_items, condition, acquisition_cost)
            logger.info(f"   💰 Market price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
            
            return {
                "suggested_price": price_data["suggested_price"],
                "comps": sold_items[:5],
                "reasoning": price_data["reasoning"],
                "projected_profit": price_data.get("projected_profit"),
                "source": "market_data",
                "research_link": research_link
            }
        
        # Try Gemini 3 Grounding (Mandatory if no comps)
        logger.info(f"🔍 Performing AI Market Research (Gemini 3 Grounding)...")
        grounded_result = self.get_ai_price_estimate(title, condition)
        
        if grounded_result:
            logger.info(f"   🌐 AI Research Price: ${grounded_result['price']:.2f}")
            return {
                "suggested_price": grounded_result['price'],
                "comps": [],
                "reasoning": grounded_result.get('reasoning', "Researched via Gemini 3"),
                "source": "ai_grounded_research",
                "research_link": research_link
            }
        
        # Fallback to AI suggestion from analyzer (image-based) ONLY if valid
        if ai_suggested_price:
            logger.info(f"   💡 Using AI image estimate: ${ai_suggested_price}")
            return {
                "suggested_price": float(ai_suggested_price),
                "comps": [],
                "reasoning": "Based on logical inference from visual analysis (No market data found)",
                "source": "ai_estimate",
                "research_link": research_link
            }
            
        # LAST RESORT: Fail Loudly (No Default)
        # User requested NO DEFAULT PRICING for undervalued items.
        logger.warning("   ❌ Price discovery failed. Manual pricing required.")
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
        logger.warning("⚠️ EBAY_APP_ID not configured - using AI fallback only")
    
    # Test with a known item
    test_title = "NTTAT CLETOP REEL TYPE A Optical Fiber Connector Cleaner"
    test_condition = "Used - Good"
    test_ai_price = "49.99"
    
    result = engine.get_price_with_comps(test_title, test_condition, ai_suggested_price=test_ai_price)
    
    logger.info(f"\n📊 Results for: {test_title[:50]}...")
    logger.info(f"   Suggested Price: ${result['suggested_price']}" if result['suggested_price'] else "   No price suggestion")
    logger.info(f"   Source: {result['source']}")
    logger.info(f"   Reasoning: {result['reasoning']}")
    logger.info(f"   🔗 Research: {result['research_link']}")
    
    if result['comps']:
        logger.info(f"\n   📦 Recent Sales ({len(result['comps'])} shown):")
        for comp in result['comps']:
            logger.info(f"      ${comp['price']:.2f} - {comp['condition']} - {comp['end_date']}")
