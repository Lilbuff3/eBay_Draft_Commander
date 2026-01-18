"""
Quick test of eBay Inventory API
"""
import json
import uuid
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
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }

# Load listing
with open(Path(__file__).parent / 'svbony_listing.json') as f:
    listing_data = json.load(f)

sku = f'DC-SVBONY-{uuid.uuid4().hex[:6].upper()}'

print(f'Creating inventory item: {sku}')

# Build aspects
aspects = {}
for key, value in listing_data.get('item_specifics', {}).items():
    if value:
        aspects[key] = [str(value)]

item = {
    'availability': {'shipToLocationAvailability': {'quantity': 1}},
    'condition': 'USED_EXCELLENT',
    'conditionDescription': 'Item is in excellent used condition.',
    'product': {
        'title': listing_data.get('title', ''),
        'description': listing_data.get('description', ''),
        'aspects': aspects
    }
}

response = requests.put(f'{INVENTORY_URL}/inventory_item/{sku}', headers=get_headers(), json=item)
print(f'Inventory item response: {response.status_code}')

if response.status_code not in [200, 201, 204]:
    print(f'Error: {response.text}')
else:
    print('✅ Inventory item created!')
    
    # Create offer (draft)
    offer = {
        'sku': sku,
        'marketplaceId': 'EBAY_US',
        'format': 'FIXED_PRICE',
        'availableQuantity': 1,
        'categoryId': '31710',  # Spotting Scopes category
        'listingDescription': listing_data.get('description', ''),
        'pricingSummary': {
            'price': {'value': str(listing_data.get('price', '79.99')), 'currency': 'USD'}
        },
        'merchantLocationKey': 'DEFAULT'
    }
    
    response = requests.post(f'{INVENTORY_URL}/offer', headers=get_headers(), json=offer)
    print(f'Offer response: {response.status_code}')
    
    if response.status_code not in [200, 201]:
        print(f'Offer error: {response.text}')
    else:
        offer_data = response.json()
        offer_id = offer_data.get('offerId')
        print(f'✅ Offer created! ID: {offer_id}')
        print(f'✅ Draft listing ready in Seller Hub!')
