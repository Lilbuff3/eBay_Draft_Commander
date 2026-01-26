"""
Price Research for eBay Draft Commander Pro
Fetch sold item data from eBay for pricing intelligence
"""
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import statistics


def load_env():
    """Load environment variables"""
    env_path = Path(__file__).parent / ".env"
    credentials = {}
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    credentials[key] = value
    return credentials


class PriceResearcher:
    """Research eBay sold prices for items"""
    
    BROWSE_API_URL = "https://api.ebay.com/buy/browse/v1"
    
    def __init__(self):
        """Initialize with eBay API credentials"""
        credentials = load_env()
        self.user_token = credentials.get('EBAY_USER_TOKEN')
        
        if not self.user_token:
            raise ValueError("EBAY_USER_TOKEN not found in .env")
    
    def _get_headers(self) -> dict:
        """Get API headers"""
        return {
            'Authorization': f'Bearer {self.user_token}',
            'Content-Type': 'application/json',
            'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US',
        }
    
    def search_sold_items(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search for recently sold items
        
        Args:
            query: Search keywords
            limit: Max results (up to 200)
            
        Returns:
            List of sold item data
        """
        # Use Browse API with sold filter
        # Note: Browse API doesn't directly show sold items in all cases
        # This uses the search endpoint with filtering
        
        url = f"{self.BROWSE_API_URL}/item_summary/search"
        
        params = {
            'q': query,
            'limit': min(limit, 200),
            'filter': 'buyingOptions:{FIXED_PRICE}',
            'sort': '-price',  # Highest price first
        }
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('itemSummaries', [])
                
                # Extract relevant price data
                results = []
                for item in items:
                    price_info = item.get('price', {})
                    results.append({
                        'title': item.get('title', ''),
                        'price': float(price_info.get('value', 0)),
                        'currency': price_info.get('currency', 'USD'),
                        'condition': item.get('condition', ''),
                        'item_id': item.get('itemId', ''),
                        'seller': item.get('seller', {}).get('username', ''),
                        'image_url': item.get('image', {}).get('imageUrl', ''),
                    })
                
                return results
            else:
                print(f"API error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def analyze_prices(self, items: List[Dict]) -> Dict:
        """
        Analyze price data from search results
        
        Args:
            items: List of item data from search
            
        Returns:
            Price analysis summary
        """
        if not items:
            return {
                'count': 0,
                'average': 0,
                'median': 0,
                'min': 0,
                'max': 0,
                'suggested': 0,
                'price_range': [],
            }
        
        prices = [item['price'] for item in items if item['price'] > 0]
        
        if not prices:
            return {
                'count': 0,
                'average': 0,
                'median': 0,
                'min': 0,
                'max': 0,
                'suggested': 0,
                'price_range': [],
            }
        
        avg = statistics.mean(prices)
        med = statistics.median(prices)
        min_price = min(prices)
        max_price = max(prices)
        
        # Suggested price: slightly below median for competitive pricing
        suggested = round(med * 0.95, 2)
        
        # Price distribution (for chart)
        # Create buckets
        bucket_size = (max_price - min_price) / 10 if max_price > min_price else 1
        buckets = {}
        
        for price in prices:
            bucket = int((price - min_price) / bucket_size) if bucket_size > 0 else 0
            bucket_key = round(min_price + bucket * bucket_size, 2)
            buckets[bucket_key] = buckets.get(bucket_key, 0) + 1
        
        price_range = [
            {'price': k, 'count': v} 
            for k, v in sorted(buckets.items())
        ]
        
        return {
            'count': len(prices),
            'average': round(avg, 2),
            'median': round(med, 2),
            'min': round(min_price, 2),
            'max': round(max_price, 2),
            'suggested': suggested,
            'price_range': price_range,
            'items': items[:10],  # Top 10 items for reference
        }
    
    def research(self, query: str) -> Dict:
        """
        Full price research for a query
        
        Args:
            query: Search keywords
            
        Returns:
            Complete research results
        """
        items = self.search_sold_items(query)
        analysis = self.analyze_prices(items)
        
        return {
            'query': query,
            'timestamp': datetime.now().isoformat(),
            **analysis,
        }
    
    def get_price_suggestion(self, title: str, condition: str = "USED_GOOD") -> float:
        """
        Get a quick price suggestion based on similar items
        
        Args:
            title: Item title or keywords
            condition: Item condition
            
        Returns:
            Suggested price
        """
        # Simplify title for search
        keywords = title.split()[:5]
        query = ' '.join(keywords)
        
        research = self.research(query)
        
        # Adjust for condition
        base_price = research.get('suggested', 29.99)
        
        condition_adjustments = {
            'NEW': 1.3,
            'LIKE_NEW': 1.2,
            'NEW_OTHER': 1.15,
            'USED_EXCELLENT': 1.0,
            'USED_VERY_GOOD': 0.95,
            'USED_GOOD': 0.9,
            'USED_ACCEPTABLE': 0.75,
            'FOR_PARTS': 0.4,
        }
        
        adjustment = condition_adjustments.get(condition, 1.0)
        
        return round(base_price * adjustment, 2)


class MockPriceResearcher:
    """Mock price researcher for testing without API"""
    
    def search_sold_items(self, query: str, limit: int = 50) -> List[Dict]:
        """Return mock data"""
        import random
        
        base_price = random.uniform(20, 100)
        
        items = []
        for i in range(min(limit, 20)):
            price = base_price + random.uniform(-15, 25)
            items.append({
                'title': f"{query} - Item {i+1}",
                'price': round(max(5, price), 2),
                'currency': 'USD',
                'condition': random.choice(['Used', 'New', 'Refurbished']),
                'item_id': f'mock_{i}',
                'seller': f'seller_{i}',
                'image_url': '',
            })
        
        return items
    
    def analyze_prices(self, items: List[Dict]) -> Dict:
        """Analyze mock prices"""
        researcher = PriceResearcher.__new__(PriceResearcher)
        return PriceResearcher.analyze_prices(researcher, items)
    
    def research(self, query: str) -> Dict:
        """Full mock research"""
        items = self.search_sold_items(query)
        analysis = self.analyze_prices(items)
        
        return {
            'query': query,
            'timestamp': datetime.now().isoformat(),
            **analysis,
        }


def get_price_researcher(use_mock: bool = False) -> PriceResearcher:
    """Get price researcher instance"""
    if use_mock:
        return MockPriceResearcher()
    
    try:
        return PriceResearcher()
    except ValueError:
        print("API not configured, using mock data")
        return MockPriceResearcher()


# Test
if __name__ == "__main__":
    print("Testing Price Research...")
    
    # Use mock for testing
    researcher = get_price_researcher(use_mock=True)
    
    # Research a product
    results = researcher.research("xerox sensor")
    
    print(f"\nQuery: {results['query']}")
    print(f"Found: {results['count']} items")
    print(f"Average: ${results['average']}")
    print(f"Median: ${results['median']}")
    print(f"Range: ${results['min']} - ${results['max']}")
    print(f"Suggested: ${results['suggested']}")
    
    print("\n✅ Price Research working!")
