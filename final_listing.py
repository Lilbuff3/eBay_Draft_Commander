"""
Create SVBONY Listing with ALL required item specifics
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

# Best category for spotting scopes - using leaf category
category_id = "31715"  # Sporting Goods > Hunting > Scopes > Spotting Scopes (leaf)

print("="*60)
print("Getting required item aspects for Spotting Scopes category")
print("="*60)

# Get item aspects
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

# Now create listing with ALL required aspects
print("\n" + "="*60)
print("Creating complete listing")
print("="*60)

with open(Path(__file__).parent / 'svbony_listing.json') as f:
    listing_data = json.load(f)

sku = f'DC-SVBONY-{uuid.uuid4().hex[:6].upper()}'
print(f"SKU: {sku}")

# Build aspects with all required fields
aspects = {
    'Brand': ['SVBONY'],
    'MPN': ['SV28'],
    'Model': ['SV28 25-75X70'],
    'Type': ['Spotting Scope'],
    'Magnification': ['25-75x'],
    'Objective Lens Diameter': ['70 mm'],
    'Focus Type': ['Dual-Speed'],
    'Features': ['Waterproof', 'Tripod Mount'],
    'Color': ['Green'],
    'Country/Region of Manufacture': ['China']
}

# Add any missing from listing data
item_specifics = listing_data.get('item_specifics', {})
for key, value in item_specifics.items():
    if value and key not in aspects:
        aspects[key] = [str(value)]

print(f"\nAspects being set:")
for k, v in aspects.items():
    print(f"  {k}: {v}")

item = {
    'availability': {'shipToLocationAvailability': {'quantity': 1}},
    'condition': 'USED_EXCELLENT',
    'conditionDescription': 'Item is in excellent used condition with minimal wear. Includes phone adapter and cleaning cloth.',
    'product': {
        'title': listing_data.get('title', 'SVBONY SV28 25-75x70 Spotting Scope Waterproof with Phone Adapter'),
        'description': listing_data.get('description', ''),
        'aspects': aspects
    }
}

print(f"\n📦 Creating inventory item...")
response = requests.put(f'{INVENTORY_URL}/inventory_item/{sku}', headers=get_headers(), json=item)
print(f"   Status: {response.status_code}")
if response.status_code not in [200, 201, 204]:
    print(f"   Error: {response.text}")
    exit(1)
print("   ✅ Done!")

# Create offer
print(f"\n📋 Creating offer...")
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
print(f"   ✅ Offer ID: {offer_id}")

# Publish
print(f"\n🚀 Publishing...")
response = requests.post(f'{INVENTORY_URL}/offer/{offer_id}/publish', headers=get_headers())
print(f"   Status: {response.status_code}")

if response.status_code in [200, 201]:
    result = response.json()
    listing_id = result.get('listingId')
    print(f"\n" + "="*60)
    print("🎉 SUCCESS! LISTING PUBLISHED!")
    print("="*60)
    print(f"\n   Listing ID: {listing_id}")
    print(f"   URL: https://www.ebay.com/itm/{listing_id}")
else:
    print(f"\n   Full error: {response.text}")
    print(f"\n📌 Draft saved. Offer ID: {offer_id}")
    print(f"   Check Seller Hub to complete and publish.")
