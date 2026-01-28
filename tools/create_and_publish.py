"""
Get correct category ID and recreate offer
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
APP_ID = credentials.get('EBAY_APP_ID')
CERT_ID = credentials.get('EBAY_CERT_ID')
FULFILLMENT_POLICY = credentials.get('EBAY_FULFILLMENT_POLICY')
PAYMENT_POLICY = credentials.get('EBAY_PAYMENT_POLICY')
RETURN_POLICY = credentials.get('EBAY_RETURN_POLICY')
MERCHANT_LOCATION = credentials.get('EBAY_MERCHANT_LOCATION')

TAXONOMY_URL = 'https://api.ebay.com/commerce/taxonomy/v1'
INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'

def get_headers():
    return {
        'Authorization': f'Bearer {USER_TOKEN}',
        'Content-Type': 'application/json',
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }

print("="*60)
print("Finding correct leaf category for SVBONY Spotting Scope")
print("="*60)

# Get category suggestions
response = requests.get(
    f'{TAXONOMY_URL}/category_tree/0/get_category_suggestions',
    headers=get_headers(),
    params={'q': 'SVBONY spotting scope 25-75x70'}
)

print(f"Category search status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    suggestions = data.get('categorySuggestions', [])
    
    print("\nCategory Suggestions:")
    for i, s in enumerate(suggestions[:5]):
        cat = s.get('category', {})
        cat_id = cat.get('categoryId')
        cat_name = cat.get('categoryName')
        
        # Build path
        ancestors = s.get('categoryTreeNodeAncestors', [])
        path_parts = [a.get('categoryName', '') for a in reversed(ancestors)]
        path_parts.append(cat_name)
        
        print(f"  {i+1}. {' > '.join(path_parts)}")
        print(f"     ID: {cat_id}")
        
        if i == 0:
            correct_category_id = cat_id
else:
    print(f"Error: {response.text}")
    correct_category_id = "181951"  # Default fallback

print(f"\n✅ Using category ID: {correct_category_id}")

# Load listing data
with open(Path(__file__).parent / 'svbony_listing.json') as f:
    listing_data = json.load(f)

# Create new inventory item with fresh SKU
sku = f'DC-SVBONY-{uuid.uuid4().hex[:6].upper()}'
print(f"\n📦 Creating inventory item: {sku}")

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
print(f"   Status: {response.status_code}")
if response.status_code not in [200, 201, 204]:
    print(f"   Error: {response.text}")
    exit(1)
print("   ✅ Inventory item created!")

# Create offer with correct category
print(f"\n📋 Creating offer with correct category...")

offer = {
    'sku': sku,
    'marketplaceId': 'EBAY_US',
    'format': 'FIXED_PRICE',
    'availableQuantity': 1,
    'categoryId': correct_category_id,
    'listingDescription': listing_data.get('description', ''),
    'listingPolicies': {
        'fulfillmentPolicyId': FULFILLMENT_POLICY,
        'paymentPolicyId': PAYMENT_POLICY,
        'returnPolicyId': RETURN_POLICY
    },
    'pricingSummary': {
        'price': {
            'value': str(listing_data.get('price', '79.99')),
            'currency': 'USD'
        }
    },
    'merchantLocationKey': MERCHANT_LOCATION
}

response = requests.post(f'{INVENTORY_URL}/offer', headers=get_headers(), json=offer)
print(f"   Status: {response.status_code}")

if response.status_code not in [200, 201]:
    print(f"   Error: {response.text}")
    exit(1)

offer_data = response.json()
offer_id = offer_data.get('offerId')
print(f"   ✅ Offer created! ID: {offer_id}")

# Publish
print(f"\n🚀 Publishing offer...")
response = requests.post(f'{INVENTORY_URL}/offer/{offer_id}/publish', headers=get_headers())
print(f"   Status: {response.status_code}")

if response.status_code in [200, 201]:
    result = response.json()
    listing_id = result.get('listingId')
    print(f"\n" + "🎉"*20)
    print(f"\n✅ LISTING PUBLISHED SUCCESSFULLY!")
    print(f"\n   Listing ID: {listing_id}")
    print(f"   URL: https://www.ebay.com/itm/{listing_id}")
    print(f"\n" + "🎉"*20)
else:
    error_data = response.json() if response.text else {}
    print(f"   Error: {response.text[:1000]}")
    print(f"\n📌 Draft created. Check Seller Hub.")
    print(f"   Offer ID: {offer_id}")
