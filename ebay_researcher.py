"""
eBay Price Researcher
Primary: Uses eBay Browse API for reliable market pricing data.
Secondary: AI-powered estimation for unique items (Gemini + Google Search)
Fallback: HTML scraping (unreliable due to bot protection).
"""
import requests
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Dict, Optional
import urllib.parse

# Import the official API client
try:
    from ebay_browse_api import eBayBrowseAPI
    HAS_BROWSE_API = True
except ImportError:
    HAS_BROWSE_API = False
    print("Warning: ebay_browse_api not found, using scraper fallback only")

# Import AI price estimator
try:
    from ai_price_estimator import AIPriceEstimator
    HAS_AI_ESTIMATOR = True
except ImportError:
    HAS_AI_ESTIMATOR = False
    print("Warning: ai_price_estimator not found, AI fallback disabled")


@dataclass
class SoldItem:
    title: str
    price: float
    shipping: float
    date: str
    condition: str
    url: str


class eBayResearcher:
    """
    Research pricing on eBay using the official Browse API.
    Falls back to scraping if API is unavailable (unreliable).
    """
    
    def __init__(self, use_api: bool = True, use_ai: bool = True):
        """
        Initialize the researcher.
        
        Args:
            use_api: If True, prefer Browse API. If False, use scraper only.
            use_ai: If True, use AI for unique items without comparables.
        """
        self._api_client = None
        self._ai_estimator = None
        self._use_api = use_api and HAS_BROWSE_API
        self._use_ai = use_ai and HAS_AI_ESTIMATOR
        
        if self._use_api:
            try:
                self._api_client = eBayBrowseAPI()
            except Exception as e:
                print(f"Warning: Browse API init failed: {e}")
                self._use_api = False
        
        if self._use_ai:
            try:
                self._ai_estimator = AIPriceEstimator()
            except Exception as e:
                print(f"Warning: AI Estimator init failed: {e}")
                self._use_ai = False

    def search_sold(self, query: str, limit: int = 30, use_ai_fallback: bool = True) -> Dict:
        """
        Search for pricing data on similar items.
        
        Args:
            query: Search keywords
            limit: Max items to retrieve
            use_ai_fallback: Use AI estimation if no market data found
            
        Returns:
            Dict with 'stats', 'items', and 'source' keys
        """
        if not query:
            return {'stats': {}, 'items': [], 'source': 'none'}

        # Try Browse API first (preferred)
        if self._use_api and self._api_client:
            try:
                result = self._api_client.search_items(query, limit)
                if result['items']:  # Got results
                    return result
            except Exception as e:
                print(f"Browse API failed, trying fallbacks: {e}")
        
        # Try AI estimation for unique items (if enabled)
        if use_ai_fallback and self._use_ai and self._ai_estimator:
            try:
                print(f"No market data found, using AI estimation for: {query}")
                result = self._ai_estimator.estimate_price(query)
                if result.get('success') and result['stats'].get('average', 0) > 0:
                    return result
            except Exception as e:
                print(f"AI estimation failed: {e}")
        
        # Last resort: scraper (unreliable)
        return self._scrape_sold_listings(query, limit)

    def _scrape_sold_listings(self, query: str, limit: int) -> Dict:
        """
        Fallback: Scrape eBay sold listings page.
        Note: This is unreliable due to eBay's bot protection.
        """
        try:
            items = self._fetch_via_scraping(query, limit)
            stats = self._calculate_stats(items)
            
            return {
                'stats': stats,
                'items': [self._item_to_dict(item) for item in items],
                'source': 'scraper_fallback'
            }
        except Exception as e:
            print(f"Scraper error: {e}")
            return {
                'stats': {'average': 0, 'median': 0, 'low': 0, 'high': 0, 'sold': 0, 'trend': 'neutral', 'trendPercent': 0},
                'items': [],
                'source': 'error'
            }

    def _fetch_via_scraping(self, query: str, limit: int) -> List[SoldItem]:
        """Fetch sold listings via HTML scraping"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        base_url = "https://www.ebay.com/sch/i.html"
        params = {
            '_nkw': query,
            'LH_Sold': '1',
            'LH_Complete': '1',
            '_ipg': '60',
        }
        
        response = requests.get(base_url, params=params, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        # Try multiple selector patterns (eBay changes these frequently)
        listings = soup.select('.s-item__wrapper')
        if not listings:
            listings = soup.select('.s-card')
        if not listings:
            listings = soup.select('[data-view="mi:1686|iid:1"]')  # Alternative pattern
        
        for item in listings:
            if len(results) >= limit:
                break
            
            try:
                # Title
                title_elem = item.select_one('.s-item__title, .s-card__title, [role="heading"]')
                if not title_elem or 'Shop on eBay' in title_elem.text:
                    continue
                title = title_elem.text.strip()
                
                # Price
                price_elem = item.select_one('.s-item__price, .s-card__price')
                if not price_elem:
                    continue
                price_text = price_elem.text.strip().replace('$', '').replace(',', '')
                price = self._parse_price(price_text)
                if price is None:
                    continue
                
                # Shipping
                shipping = 0.0
                ship_elem = item.select_one('.s-item__shipping, .s-card__shipping')
                if ship_elem:
                    ship_text = ship_elem.text.strip()
                    if 'Free' not in ship_text:
                        ship_clean = re.sub(r'[^\d.]', '', ship_text)
                        if ship_clean:
                            shipping = float(ship_clean)
                
                # Date
                date_elem = item.select_one('.s-item__title--tagblock .POSITIVE, .POSITIVE')
                date = date_elem.text.replace('Sold ', '').strip() if date_elem else "Unknown"
                
                # URL
                link_elem = item.select_one('.s-item__link, a[href*="ebay.com/itm"]')
                url = link_elem['href'] if link_elem else ""
                
                results.append(SoldItem(
                    title=title,
                    price=price,
                    shipping=shipping,
                    date=date,
                    condition="Used",
                    url=url
                ))
            except Exception:
                continue
        
        return results

    def _parse_price(self, price_str: str) -> Optional[float]:
        """Extract numeric price from string"""
        try:
            matches = re.findall(r"[\d.]+", price_str)
            if matches:
                return float(matches[0])
            return None
        except:
            return None

    def _calculate_stats(self, items: List[SoldItem]) -> Dict:
        """Calculate pricing statistics"""
        if not items:
            return {
                'average': 0, 'median': 0, 'low': 0, 'high': 0,
                'sold': 0, 'trend': 'neutral', 'trendPercent': 0
            }
        
        prices = sorted([i.price for i in items])
        avg_price = sum(prices) / len(prices)
        median_price = prices[len(prices) // 2]
        
        return {
            'average': round(avg_price, 2),
            'median': round(median_price, 2),
            'low': round(prices[0], 2),
            'high': round(prices[-1], 2),
            'sold': len(items),
            'trend': 'up' if avg_price > median_price else 'neutral',
            'trendPercent': 0
        }

    def _item_to_dict(self, item: SoldItem) -> Dict:
        """Convert SoldItem to dict"""
        return {
            'title': item.title,
            'price': item.price,
            'shipping': item.shipping,
            'date': item.date,
            'condition': item.condition,
            'url': item.url
        }


# Test
if __name__ == "__main__":
    print("Testing eBay Researcher...")
    print("=" * 50)
    
    researcher = eBayResearcher()
    result = researcher.search_sold("vintage camera")
    
    print(f"\nSource: {result.get('source', 'unknown')}")
    print(f"Found {len(result['items'])} items")
    
    stats = result['stats']
    if stats.get('average', 0) > 0:
        print(f"Average: ${stats['average']:.2f}")
        print(f"Median:  ${stats['median']:.2f}")
        print(f"Range:   ${stats['low']:.2f} - ${stats['high']:.2f}")
    else:
        print("No pricing data available")

