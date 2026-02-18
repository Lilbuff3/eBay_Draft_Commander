import sys
from pathlib import Path

sys.path.append("c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander")

import requests
from backend.app.services.ebay.policies import _get_headers

def fetch_locations():
    """Fetch all defined inventory locations"""
    print("🌍 Fetching eBay Inventory Locations...")
    
    INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
    
    try:
        response = requests.get(
            f'{INVENTORY_URL}/location',
            headers=_get_headers(),
            params={'limit': 100}
        )
        
        if response.status_code == 200:
            data = response.json()
            locations = data.get('locations', [])
            print(f"✅ Found {len(locations)} locations:\n")
            
            for loc in locations:
                print(f"   🔑 Key: {loc.get('merchantLocationKey')}")
                print(f"      Name: {loc.get('name')}")
                print(f"      Description: {loc.get('location', {}).get('address')}")
                import json
                print(json.dumps(loc, indent=2))
                print("-" * 30)
                
            if locations:
                print("\n💡 Recommendation: Add one of these keys to your .env file as EBAY_MERCHANT_LOCATION")
            else:
                print("\n⚠️ No locations found! You need to create one.")
                
        else:
            print(f"❌ Error fetching locations: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    fetch_locations()
