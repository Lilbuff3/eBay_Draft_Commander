"""
Pricing Engine for eBay Draft Commander
Uses eBay Finding API to get sold listings and calculate market-based prices
"""
import os
import statistics
import requests
from pathlib import Path
from urllib.parse import quote


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
    }
    
    def __init__(self):
        """Initialize with eBay App ID from .env"""
        env_path = Path(__file__).parent / ".env"
        self.app_id = None
        
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('EBAY_APP_ID='):
                        self.app_id = line.split('=')[1].strip()
                        break
        
        if not self.app_id:
            print("⚠️ EBAY_APP_ID not found in .env - Pricing Intelligence disabled")
            
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
                print("✅ Pricing AI initialized (Gemini 3 + Search Grounding)")
            except Exception as e:
                print(f"⚠️ Could not initialize Pricing AI: {e}")
    
    def search_sold_listings(self, keywords, category_id=None, limit=15):
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
        
        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.0.0",
            "SECURITY-APPNAME": self.app_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "REST-PAYLOAD": "",
            "keywords": keywords,
            "itemFilter(0).name": "SoldItemsOnly",
            "itemFilter(0).value": "true",
            "paginationInput.entriesPerPage": str(limit),
            "sortOrder": "EndTimeSoonest",  # Most recent first
        }
        
        if category_id:
            params["categoryId"] = str(category_id)
        
        try:
            response = requests.get(self.FINDING_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Navigate the complex response structure
            result = data.get("findCompletedItemsResponse", [{}])[0]
            ack = result.get("ack", ["Failure"])[0]
            
            if ack != "Success":
                error_msg = result.get("errorMessage", [{}])[0].get("error", [{}])[0].get("message", ["Unknown error"])[0]
                print(f"⚠️ Finding API error: {error_msg}")
                return []
            
            search_result = result.get("searchResult", [{}])[0]
            items = search_result.get("item", [])
            
            sold_items = []
            for item in items:
                try:
                    title = item.get("title", [""])[0]
                    
                    # Get price
                    selling_status = item.get("sellingStatus", [{}])[0]
                    current_price = selling_status.get("currentPrice", [{}])[0]
                    price = float(current_price.get("__value__", 0))
                    currency = current_price.get("@currencyId", "USD")
                    
                    # Get condition
                    condition_info = item.get("condition", [{}])[0]
                    condition = condition_info.get("conditionDisplayName", ["Unknown"])[0]
                    
                    # Get end date
                    listing_info = item.get("listingInfo", [{}])[0]
                    end_time = listing_info.get("endTime", [""])[0]
                    
                    # Get URL
                    url = item.get("viewItemURL", [""])[0]
                    
                    sold_items.append({
                        "title": title,
                        "price": price,
                        "currency": currency,
                        "condition": condition,
                        "end_date": end_time[:10] if end_time else "",  # Just the date part
                        "url": url
                    })
                except (KeyError, IndexError, ValueError) as e:
                    continue  # Skip malformed items
            
            return sold_items
            
        except requests.RequestException as e:
            print(f"❌ Finding API request failed: {e}")
            return []
        except Exception as e:
            print(f"❌ Pricing engine error: {e}")
            return []
    
    def calculate_suggested_price(self, sold_items, our_condition="Used - Good"):
        """
        Calculate a suggested price based on sold items data.
        
        Uses median price (robust to outliers) with condition adjustment.
        
        Args:
            sold_items: List of dicts from search_sold_listings()
            our_condition: The condition of our item
        
        Returns:
            Dict with: suggested_price, comp_count, median_price, reasoning
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
        multiplier = self.CONDITION_MULTIPLIERS.get(our_condition, 0.75)
        
        # Calculate suggested price
        suggested_price = round(median_price * multiplier, 2)
        
        # Smart pricing: round to .99 or .95
        if suggested_price > 10:
            suggested_price = round(suggested_price) - 0.01  # e.g., 45.00 -> 44.99
        
        return {
            "suggested_price": suggested_price,
            "comp_count": len(prices),
            "median_price": round(median_price, 2),
            "multiplier": multiplier,
            "reasoning": f"Median of {len(prices)} sales (${median_price:.2f}) × {multiplier:.0%} condition adjustment"
        }
    
    def generate_ebay_search_link(self, title):
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
    
    def get_ai_price_estimate(self, title, condition):
        """Estimate price using Gemini 3 with Google Search grounding"""
        if not self.ai_client:
            return None
            
        try:
            from google.genai import types
            
            prompt = f"""Search for the current market value of this item specifically for eBay:
            Item: {title}
            Condition: {condition}
            
            Return ONLY a number representing the suggested price in USD. No symbols, no text."""
            
            response = self.ai_client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.0
                )
            )
            
            # Extract number
            price_text = response.text.strip().replace('$', '').replace(',', '')
            import re
            match = re.search(r'\d+\.?\d*', price_text)
            if match:
                return float(match.group())
        except Exception as e:
            print(f"   ⚠️ Gemini 3 Grounding failed: {e}")
            
        return None

    def get_price_with_comps(self, title, condition="Used - Good", category_id=None, ai_suggested_price=None):
        """
        Main entry point: Get suggested price and comparable sales data.
        Falls back to AI suggestion if API fails.
        
        Args:
            title: The item title (used as search keywords)
            condition: The item's condition
            category_id: Optional category to narrow search
            ai_suggested_price: Fallback price from AI analyzer
        
        Returns:
            Dict with: suggested_price, comps, reasoning, source, research_link
        """
        # Generate research link for user
        research_link = self.generate_ebay_search_link(title)
        
        # Clean up title for search (remove special chars, limit length)
        search_query = " ".join(title.split()[:8])  # First 8 words
        
        print(f"🔍 Searching sold listings for: {search_query[:50]}...")
        
        sold_items = self.search_sold_listings(search_query, category_id, limit=15)
        
        if sold_items:
            price_data = self.calculate_suggested_price(sold_items, condition)
            print(f"   💰 Market price: ${price_data['suggested_price']:.2f} ({price_data['reasoning']})")
            
            return {
                "suggested_price": price_data["suggested_price"],
                "comps": sold_items[:5],
                "reasoning": price_data["reasoning"],
                "source": "market_data",
                "research_link": research_link
            }
        
        # Try Gemini 3 Grounding if market data fails or as enhancement
        if not sold_items:
            print(f"🔍 Performing AI Market Research (Gemini 3 Grounding)...")
            grounded_price = self.get_ai_price_estimate(title, condition)
            if grounded_price:
                print(f"   🌐 AI Research Price: ${grounded_price:.2f}")
                return {
                    "suggested_price": grounded_price,
                    "comps": [],
                    "reasoning": "Researched via Gemini 3 with Google Search grounding",
                    "source": "ai_grounded_research",
                    "research_link": research_link
                }
        
        # Fallback to AI suggestion from analyzer (image-based)
        if ai_suggested_price:
            print(f"   💡 Using AI image estimate: ${ai_suggested_price}")
            return {
                "suggested_price": float(ai_suggested_price),
                "comps": [],
                "reasoning": "Based on AI image analysis (no market data found)",
                "source": "ai_estimate",
                "research_link": research_link
            }
        
        print("   ⚠️ No pricing data available")
        return {
            "suggested_price": None,
            "comps": [],
            "reasoning": "No comparable sales found and AI research failed",
            "source": "none",
            "research_link": research_link
        }


# Test the pricing engine
if __name__ == "__main__":
    print("Testing Pricing Engine...\n")
    
    engine = PricingEngine()
    
    if not engine.app_id:
        print("⚠️ EBAY_APP_ID not configured - using AI fallback only")
    
    # Test with a known item
    test_title = "NTTAT CLETOP REEL TYPE A Optical Fiber Connector Cleaner"
    test_condition = "Used - Good"
    test_ai_price = "49.99"
    
    result = engine.get_price_with_comps(test_title, test_condition, ai_suggested_price=test_ai_price)
    
    print(f"\n📊 Results for: {test_title[:50]}...")
    print(f"   Suggested Price: ${result['suggested_price']}" if result['suggested_price'] else "   No price suggestion")
    print(f"   Source: {result['source']}")
    print(f"   Reasoning: {result['reasoning']}")
    print(f"   🔗 Research: {result['research_link']}")
    
    if result['comps']:
        print(f"\n   📦 Recent Sales ({len(result['comps'])} shown):")
        for comp in result['comps']:
            print(f"      ${comp['price']:.2f} - {comp['condition']} - {comp['end_date']}")
