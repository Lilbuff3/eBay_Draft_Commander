"""
eBay Browse API Client for Price Research
Uses the official Browse API to get current market prices for similar items.
"""
import base64
import requests
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class MarketItem:
    """Represents an item from market research"""
    title: str
    price: float
    condition: str
    image_url: str
    item_url: str
    seller: str


class eBayBrowseAPI:
    """
    Client for eBay Browse API - used for price research.
    
    Uses OAuth2 Client Credentials flow to search active listings
    and calculate market pricing statistics.
    """
    
    AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    BROWSE_URL = "https://api.ebay.com/buy/browse/v1"
    
    def __init__(self):
        self.load_credentials()
        self._access_token = None
    
    def load_credentials(self):
        """Load API credentials from .env file"""
        env_path = Path(__file__).resolve().parents[4] / ".env"
        
        if not env_path.exists():
            raise FileNotFoundError(f"No .env file found at {env_path}")
        
        credentials = {}
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()
        
        self.app_id = credentials.get('EBAY_APP_ID')
        self.cert_id = credentials.get('EBAY_CERT_ID')
        
        if not all([self.app_id, self.cert_id]):
            raise ValueError("Missing EBAY_APP_ID or EBAY_CERT_ID in .env file")
    
    def get_access_token(self) -> Optional[str]:
        """Get OAuth access token using Client Credentials Grant"""
        if self._access_token:
            return self._access_token
        
        credentials = f"{self.app_id}:{self.cert_id}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }
        
        try:
            response = requests.post(self.AUTH_URL, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data['access_token']
            return self._access_token
        except requests.exceptions.RequestException as e:
            print(f"❌ Browse API auth failed: {e}")
            return None
    
    def search_items(self, query: str, limit: int = 30) -> Dict:
        """
        Search for items matching query and return pricing statistics.
        
        Args:
            query: Search keywords
            limit: Max items to retrieve (default 30)
            
        Returns:
            Dict with 'stats' and 'items' keys
        """
        token = self.get_access_token()
        if not token:
            return self._empty_result()
        
        url = f"{self.BROWSE_URL}/item_summary/search"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "X-EBAY-C-ENDUSERCTX": "affiliateCampaignId=<ePNCampaignId>,affiliateReferenceId=<referenceId>"
        }
        
        params = {
            "q": query,
            "limit": min(limit, 50),  # API max is 200, but we keep it reasonable
            "filter": "buyingOptions:{FIXED_PRICE}"  # Only Buy It Now for clean pricing
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = self._parse_items(data.get('itemSummaries', []))
            stats = self._calculate_stats(items)
            
            return {
                'stats': stats,
                'items': [self._item_to_dict(item) for item in items],
                'source': 'browse_api'
            }
        except requests.exceptions.RequestException as e:
            print(f"❌ Browse API search failed: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.text[:500]}")
            return self._empty_result()
    
    def _parse_items(self, summaries: List[Dict]) -> List[MarketItem]:
        """Parse API response into MarketItem objects"""
        items = []
        
        for summary in summaries:
            try:
                # Extract price
                price_info = summary.get('price', {})
                price_str = price_info.get('value', '0')
                price = float(price_str)
                
                # Skip items with no price or unreasonable prices
                if price <= 0 or price > 100000:
                    continue
                
                # Extract other fields
                title = summary.get('title', 'Unknown')
                condition = summary.get('condition', 'Unknown')
                image = summary.get('image', {}).get('imageUrl', '')
                item_url = summary.get('itemWebUrl', '')
                seller = summary.get('seller', {}).get('username', 'Unknown')
                
                items.append(MarketItem(
                    title=title,
                    price=price,
                    condition=condition,
                    image_url=image,
                    item_url=item_url,
                    seller=seller
                ))
            except (ValueError, KeyError):
                continue
        
        return items
    
    def _calculate_stats(self, items: List[MarketItem]) -> Dict:
        """Calculate pricing statistics from items"""
        if not items:
            return {
                'average': 0, 'median': 0, 'low': 0, 'high': 0,
                'sold': 0, 'trend': 'neutral', 'trendPercent': 0
            }
        
        prices = sorted([item.price for item in items])
        
        avg_price = sum(prices) / len(prices)
        median_price = prices[len(prices) // 2]
        low_price = prices[0]
        high_price = prices[-1]
        
        # Determine trend based on median vs average
        if avg_price > median_price * 1.1:
            trend = 'up'
            trend_pct = round((avg_price - median_price) / median_price * 100, 1)
        elif avg_price < median_price * 0.9:
            trend = 'down'
            trend_pct = round((median_price - avg_price) / median_price * 100, 1)
        else:
            trend = 'neutral'
            trend_pct = 0
        
        return {
            'average': round(avg_price, 2),
            'median': round(median_price, 2),
            'low': round(low_price, 2),
            'high': round(high_price, 2),
            'sold': len(items),  # Note: These are active listings, not sold
            'trend': trend,
            'trendPercent': trend_pct
        }
    
    def _item_to_dict(self, item: MarketItem) -> Dict:
        """Convert MarketItem to dict for JSON serialization"""
        return {
            'title': item.title,
            'price': item.price,
            'shipping': 0,  # Browse API doesn't always include shipping
            'date': 'Active',  # These are active listings
            'condition': item.condition,
            'url': item.item_url
        }
    
    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            'stats': {
                'average': 0, 'median': 0, 'low': 0, 'high': 0,
                'sold': 0, 'trend': 'neutral', 'trendPercent': 0
            },
            'items': [],
            'source': 'browse_api'
        }


# Test the Browse API client
if __name__ == "__main__":
    print("Testing eBay Browse API Client...")
    print("=" * 50)
    
    try:
        client = eBayBrowseAPI()
        
        # Test search
        query = "vintage camera"
        print(f"\n🔍 Searching for: '{query}'")
        
        results = client.search_items(query, limit=10)
        
        print(f"\n📊 Statistics:")
        stats = results['stats']
        print(f"   Average: ${stats['average']:.2f}")
        print(f"   Median:  ${stats['median']:.2f}")
        print(f"   Low:     ${stats['low']:.2f}")
        print(f"   High:    ${stats['high']:.2f}")
        print(f"   Count:   {stats['sold']}")
        print(f"   Trend:   {stats['trend']} ({stats['trendPercent']}%)")
        
        print(f"\n📦 Sample Items:")
        for i, item in enumerate(results['items'][:5], 1):
            print(f"   {i}. {item['title'][:50]}...")
            print(f"      ${item['price']:.2f} - {item['condition']}")
        
        print(f"\n✅ Browse API test complete! Source: {results['source']}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
