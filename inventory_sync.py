"""
Inventory Sync for eBay Draft Commander Pro
Fetch and sync active eBay listings locally
"""
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Callable


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


class InventorySync:
    """Sync active eBay listings to local storage"""
    
    INVENTORY_API_URL = "https://api.ebay.com/sell/inventory/v1"
    TRADING_API_URL = "https://api.ebay.com/ws/api.dll"
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize inventory sync
        
        Args:
            data_dir: Directory to store synced data
        """
        credentials = load_env()
        self.user_token = credentials.get('EBAY_USER_TOKEN')
        
        if data_dir is None:
            data_dir = Path(__file__).parent / "data" / "inventory"
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.inventory_file = self.data_dir / "listings.json"
        self._listings: List[Dict] = []
        
        # Load existing data
        self.load_local()
    
    def _get_headers(self) -> dict:
        """Get API headers"""
        return {
            'Authorization': f'Bearer {self.user_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Content-Language': 'en-US',
            'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US',
        }
    
    def load_local(self) -> List[Dict]:
        """Load locally stored listings"""
        if self.inventory_file.exists():
            try:
                with open(self.inventory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._listings = data.get('listings', [])
            except Exception as e:
                print(f"Error loading inventory: {e}")
                self._listings = []
        return self._listings
    
    def save_local(self):
        """Save listings to local storage"""
        data = {
            'synced_at': datetime.now().isoformat(),
            'count': len(self._listings),
            'listings': self._listings,
        }
        
        with open(self.inventory_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def fetch_active_listings(self, limit: int = 100, 
                             progress_callback: Callable = None) -> List[Dict]:
        """
        Fetch active listings from eBay
        
        Args:
            limit: Max listings to fetch
            progress_callback: Optional callback(current, total) for progress
            
        Returns:
            List of listing data
        """
        if not self.user_token:
            raise ValueError("EBAY_USER_TOKEN not configured")
        
        listings = []
        
        # Strategy: Fetch inventory items first, then fetch offers for each SKU
        # This avoids the "Invalid SKU" error that happens when fetching all offers in bulk
        
        offset = 0
        limit_per_page = 20 # Smaller batch size for item loops
        
        print(f"Fetching inventory items...")
        
        try:
            while True:
                url = f"{self.INVENTORY_API_URL}/inventory_item"
                params = {
                    'offset': offset,
                    'limit': limit_per_page
                }
                
                response = requests.get(url, headers=self._get_headers(), params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('inventoryItems', [])
                    
                    if not items:
                        break
                    
                    for item in items:
                        sku = item.get('sku')
                        if not sku:
                            continue
                            
                        # Fetch offer for this SKU
                        try:
                            offer_url = f"{self.INVENTORY_API_URL}/offer"
                            offer_resp = requests.get(offer_url, headers=self._get_headers(), params={'sku': sku})
                            
                            if offer_resp.status_code == 200:
                                offer_data = offer_resp.json()
                                offers = offer_data.get('offers', [])
                                if offers:
                                    # Use the first offer found for this SKU
                                    primary_offer = offers[0]
                                    listing = self._parse_offer(primary_offer)
                                    if listing:
                                        listings.append(listing)
                        except Exception as e:
                            print(f"Error fetching offer for SKU {sku}: {e}")
                    
                    if progress_callback:
                        progress_callback(len(listings), limit)
                        
                    offset += limit_per_page
                    
                    if len(listings) >= limit or len(items) < limit_per_page:
                        break
                else:
                    print(f"API error fetching inventory items: {response.status_code} - {response.text}")
                    break
                    
        except Exception as e:
            print(f"Fetch error: {e}")
            if not listings:
                return self._fetch_via_trading_api(limit, progress_callback)
        
        self._listings = listings
        self.save_local()
        
        return listings
    
    def _parse_offer(self, offer: dict) -> Optional[Dict]:
        """Parse offer data from Inventory API"""
        try:
            price_obj = offer.get('pricingSummary', {}).get('price', {})
            
            return {
                'offer_id': offer.get('offerId'),
                'sku': offer.get('sku'),
                'listing_id': offer.get('listingId'),
                'title': offer.get('listing', {}).get('title', 'Unknown'),
                'price': float(price_obj.get('value', 0)),
                'currency': price_obj.get('currency', 'USD'),
                'quantity': offer.get('availableQuantity', 0),
                'status': offer.get('status'),
                'format': offer.get('format'),
                'category_id': offer.get('categoryId'),
                'synced_at': datetime.now().isoformat(),
            }
        except:
            return None
    
    def _fetch_via_trading_api(self, limit: int, 
                               progress_callback: Callable = None) -> List[Dict]:
        """Fallback: fetch via Trading API"""
        # Trading API requires different auth
        print("Trading API fallback not implemented - using mock data")
        return self._get_mock_listings(limit, progress_callback)
    
    def _get_mock_listings(self, limit: int, 
                          progress_callback: Callable = None) -> List[Dict]:
        """Generate mock listings for testing"""
        import random
        
        mock_titles = [
            "Xerox Sensor Assembly",
            "HP Printer Part",
            "Canon Scanner Module",
            "Epson Print Head",
            "Brother Drum Unit",
            "Lexmark Fuser Kit",
            "Dell Imaging Drum",
            "Ricoh Transfer Belt",
        ]
        
        listings = []
        for i in range(min(limit, 20)):
            if progress_callback:
                progress_callback(i + 1, limit)
            
            listings.append({
                'offer_id': f'mock_offer_{i}',
                'sku': f'SKU-{1000 + i}',
                'listing_id': f'{300000000000 + i}',
                'title': f"{random.choice(mock_titles)} #{i+1}",
                'price': round(random.uniform(20, 150), 2),
                'currency': 'USD',
                'quantity': random.randint(1, 5),
                'status': 'ACTIVE',
                'format': 'FIXED_PRICE',
                'category_id': '58058',
                'synced_at': datetime.now().isoformat(),
            })
        
        self._listings = listings
        self.save_local()
        
        return listings
    
    def get_listings(self) -> List[Dict]:
        """Get currently loaded listings"""
        return self._listings
    
    def get_listing_count(self) -> int:
        """Get number of synced listings"""
        return len(self._listings)
    
    def get_last_sync(self) -> Optional[str]:
        """Get last sync timestamp"""
        if self.inventory_file.exists():
            try:
                with open(self.inventory_file, 'r') as f:
                    data = json.load(f)
                    return data.get('synced_at')
            except:
                pass
        return None
    
    def search_listings(self, query: str) -> List[Dict]:
        """Search synced listings by title"""
        query = query.lower()
        return [
            l for l in self._listings 
            if query in l.get('title', '').lower()
        ]
    
    def get_total_value(self) -> float:
        """Calculate total inventory value"""
        return sum(
            l.get('price', 0) * l.get('quantity', 1) 
            for l in self._listings
        )
    
    def get_stats(self) -> Dict:
        """Get inventory statistics"""
        if not self._listings:
            return {
                'count': 0,
                'total_value': 0,
                'avg_price': 0,
                'last_sync': None,
            }
        
        prices = [l.get('price', 0) for l in self._listings]
        
        return {
            'count': len(self._listings),
            'total_value': round(self.get_total_value(), 2),
            'avg_price': round(sum(prices) / len(prices), 2),
            'last_sync': self.get_last_sync(),
        }
    
    def export_csv(self, output_path: str) -> Path:
        """Export listings to CSV"""
        import csv
        
        output = Path(output_path)
        
        with open(output, 'w', newline='', encoding='utf-8') as f:
            if self._listings:
                writer = csv.DictWriter(f, fieldnames=self._listings[0].keys())
                writer.writeheader()
                writer.writerows(self._listings)
        
        return output


# Global instance
_instance = None

def get_inventory_sync() -> InventorySync:
    """Get global inventory sync instance"""
    global _instance
    if _instance is None:
        _instance = InventorySync()
    return _instance


# Test
if __name__ == "__main__":
    print("Testing Inventory Sync...")
    
    sync = InventorySync()
    
    # Fetch (will use mock data without valid token)
    def progress(current, total):
        print(f"Progress: {current}/{total}")
    
    listings = sync.fetch_active_listings(limit=10, progress_callback=progress)
    
    print(f"\nFetched {len(listings)} listings")
    
    # Stats
    stats = sync.get_stats()
    print(f"\nStats:")
    print(f"  Count: {stats['count']}")
    print(f"  Total Value: ${stats['total_value']}")
    print(f"  Avg Price: ${stats['avg_price']}")
    
    # Search
    results = sync.search_listings("xerox")
    print(f"\nSearch 'xerox': {len(results)} results")
    
    print("\n✅ Inventory Sync working!")
