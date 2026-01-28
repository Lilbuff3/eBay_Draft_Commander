"""
List all Inventory Items and Offers in the account
"""
import json
import requests
from pathlib import Path

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

credentials = load_env()
USER_TOKEN = credentials.get('EBAY_USER_TOKEN')

INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'

def get_headers():
    return {
        'Authorization': f'Bearer {USER_TOKEN}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

print("="*70)
print("📦 Inventory Items (created via API)")
print("="*70)

response = requests.get(
    f'{INVENTORY_URL}/inventory_item',
    headers=get_headers(),
    params={'limit': 50}
)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    items = data.get('inventoryItems', [])
    total = data.get('total', len(items))
    
    print(f"Total inventory items: {total}")
    
    for item in items:
        sku = item.get('sku')
        product = item.get('product', {})
        title = product.get('title', 'No title')[:50]
        aspects = product.get('aspects', {})
        brand = aspects.get('Brand', [''])[0] if aspects.get('Brand') else ''
        
        print(f"\n  • SKU: {sku}")
        print(f"    Title: {title}")
        if brand:
            print(f"    Brand: {brand}")
else:
    print(f"Error: {response.text[:500]}")

print("\n" + "="*70)
print("📋 Offers (unpublished drafts)")
print("="*70)

response = requests.get(
    f'{INVENTORY_URL}/offer',
    headers=get_headers(),
    params={'limit': 50}
)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    offers = data.get('offers', [])
    total = data.get('total', len(offers))
    
    print(f"Total offers: {total}")
    
    for offer in offers:
        offer_id = offer.get('offerId')
        sku = offer.get('sku')
        status = offer.get('status')
        listing_id = offer.get('listingId', 'Not published')
        category = offer.get('categoryId')
        price_data = offer.get('pricingSummary', {}).get('price', {})
        price = f"${price_data.get('value', '?')} {price_data.get('currency', '')}"
        
        print(f"\n  • Offer ID: {offer_id}")
        print(f"    SKU: {sku}")
        print(f"    Status: {status}")
        print(f"    Category: {category}")
        print(f"    Price: {price}")
        if listing_id != 'Not published':
            print(f"    Listing: https://www.ebay.com/itm/{listing_id}")
else:
    print(f"Error: {response.text[:500]}")
