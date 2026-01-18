"""
Create eBay Listing - Using Cameras & Photo category instead
Spotting scope 31715 requires specific magnification values not suitable for 25-75x
Let's try Telescopes & Binoculars > Spotting Scopes
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

# Try a different category approach - let eBay suggest based on title
print("Getting best category from eBay...")

response = requests.get(
    f'{TAXONOMY_URL}/category_tree/0/get_category_suggestions',
    headers=get_headers(),
    params={'q': 'SVBONY SV28 spotting scope bird watching'}
)

if response.status_code == 200:
    data = response.json()
    suggestions = data.get('categorySuggestions', [])
    
    print(f"Found {len(suggestions)} category suggestions")
    
    # Find a leaf category
    for s in suggestions:
        cat = s.get('category', {})
        cat_id = cat.get('categoryId')
        cat_name = cat.get('categoryName')
        
        ancestors = s.get('categoryTreeNodeAncestors', [])
        path_parts = [a.get('categoryName', '') for a in reversed(ancestors)]
        path_parts.append(cat_name)
        full_path = ' > '.join(path_parts)
        
        print(f"  {cat_id}: {full_path}")

# Try category 181951 - this is Cameras & Photo > Telescopes & Binoculars > Spotting Scopes
category_id = "181951"  # Cameras & Photo > Binoculars & Telescopes > Spotting Scopes

print(f"\nUsing category: {category_id}")

# Check required aspects for this category
print("\nChecking required aspects...")
response = requests.get(
    f'{TAXONOMY_URL}/category_tree/0/get_item_aspects_for_category',
    headers=get_headers(),
    params={'category_id': category_id}
)

required_aspects = []
if response.status_code == 200:
    data = response.json()
    for aspect in data.get('aspects', []):
        constraint = aspect.get('aspectConstraint', {})
        if constraint.get('aspectRequired'):
            name = aspect.get('localizedAspectName')
            required_aspects.append(name)
            print(f"  Required: {name}")

# Now create the listing
print("\n" + "="*60)
print("Creating listing")
print("="*60)

with open(Path(__file__).parent / 'svbony_listing.json') as f:
    listing_data = json.load(f)

sku = f'DC-SVBONY-{uuid.uuid4().hex[:6].upper()}'
print(f"SKU: {sku}")

# Build aspects matching eBay requirements
aspects = {
    'Brand': ['SVBONY'],
    'MPN': ['SV28'],
    'Model': ['SV28 25-75X70'],
    'Type': ['Spotting Scope']
}

# Add magnification if required
if 'Magnification' in required_aspects:
    aspects['Magnification'] = ['25-75x']

if 'Maximum Magnification' in required_aspects:
    aspects['Maximum Magnification'] = ['75x']

if 'Objective Lens Diameter' in required_aspects:
    aspects['Objective Lens Diameter'] = ['70 mm']

print(f"Aspects: {aspects}")

item = {
    'availability': {'shipToLocationAvailability': {'quantity': 1}},
    'condition': 'USED_EXCELLENT',
    'conditionDescription': 'Excellent used condition with minimal wear.',
    'product': {
        'title': listing_data.get('title', 'SVBONY SV28 25-75x70 Spotting Scope'),
        'description': listing_data.get('description', ''),
        'aspects': aspects
    }
}

print("\n📦 Creating inventory item...")
response = requests.put(f'{INVENTORY_URL}/inventory_item/{sku}', headers=get_headers(), json=item)
print(f"   Status: {response.status_code}")
if response.status_code not in [200, 201, 204]:
    print(f"   Error: {response.text}")
    exit(1)

# Create offer
print("\n📋 Creating offer...")
offer = {
    'sku': sku,
    'marketplaceId': 'EBAY_US',
    'format': 'FIXED_PRICE',
    'availableQuantity': 1,
    'categoryId': category_id,
    'listingDescription': listing_data.get('description', ''),
    'listingPolicies': {
        'fulfillmentPolicyId': FULFILLMENT_POLICY,
        'paymentPolicyId': PAYMENT_POLICY,
        'returnPolicyId': RETURN_POLICY
    },
    'pricingSummary': {
        'price': {'value': str(listing_data.get('price', '79.99')), 'currency': 'USD'}
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
print(f"   ✅ Offer ID: {offer_id}")

# Publish
print("\n🚀 Publishing...")
response = requests.post(f'{INVENTORY_URL}/offer/{offer_id}/publish', headers=get_headers())
print(f"   Status: {response.status_code}")

if response.status_code in [200, 201]:
    result = response.json()
    listing_id = result.get('listingId')
    print(f"\n" + "🎉"*20)
    print(f"\n✅ SUCCESS! LISTING PUBLISHED!")
    print(f"\n   Listing ID: {listing_id}")
    print(f"   URL: https://www.ebay.com/itm/{listing_id}")
    print(f"\n" + "🎉"*20)
else:
    print(f"\n   Error: {response.text}")
    print(f"\n📌 Draft saved. Offer ID: {offer_id}")
    print("   Complete in Seller Hub: https://www.ebay.com/sh/lst/drafts")
