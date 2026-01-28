"""
List all inventory items and offers with full details
"""
import requests
from pathlib import Path
import json

def load_env():
    env_path = Path(__file__).parent / ".env"
    credentials = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                credentials[key.strip()] = value.strip()
    return credentials

c = load_env()
token = c.get('EBAY_USER_TOKEN')

headers = {
    'Authorization': 'Bearer ' + token,
    'Accept': 'application/json'
}

print("="*70)
print("INVENTORY ITEMS (via API)")
print("="*70)

r = requests.get('https://api.ebay.com/sell/inventory/v1/inventory_item', 
                 headers=headers, params={'limit': 50})
print(f"Status: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    total = data.get('total', 0)
    print(f"Total: {total}")
    
    for item in data.get('inventoryItems', []):
        sku = item.get('sku')
        title = item.get('product', {}).get('title', 'No title')[:50]
        print(f"\n  SKU: {sku}")
        print(f"  Title: {title}")
else:
    print(f"Error: {r.text[:200]}")

print("\n" + "="*70)
print("OFFERS (unpublished)")  
print("="*70)

# Get offers for each SKU
if r.status_code == 200:
    for item in data.get('inventoryItems', [])[:5]:
        sku = item.get('sku')
        
        r2 = requests.get(f'https://api.ebay.com/sell/inventory/v1/offer',
                         headers=headers, params={'sku': sku})
        
        if r2.status_code == 200:
            offers = r2.json().get('offers', [])
            for offer in offers:
                print(f"\n  SKU: {sku}")
                print(f"  Offer ID: {offer.get('offerId')}")
                print(f"  Status: {offer.get('status')}")
                print(f"  Category: {offer.get('categoryId')}")
                listing_id = offer.get('listingId')
                if listing_id:
                    print(f"  LIVE: https://www.ebay.com/itm/{listing_id}")
