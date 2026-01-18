"""
Debug: Find a category that works with minimal requirements
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
        'Authorization': 'Bearer ' + USER_TOKEN,
        'Content-Type': 'application/json',
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }

# Step 1: Get a category suggestion
print("1. Finding category...")
response = requests.get(
    TAXONOMY_URL + '/category_tree/0/get_category_suggestions',
    headers=get_headers(),
    params={'q': 'fiber optic cleaning tool'}
)

if response.status_code == 200:
    data = response.json()
    suggestions = data.get('categorySuggestions', [])
    if suggestions:
        category_id = suggestions[0].get('category', {}).get('categoryId')
        category_name = suggestions[0].get('category', {}).get('categoryName')
        print("   Category:", category_id, "-", category_name)
    else:
        category_id = "293"  # Fallback
else:
    category_id = "293"

# Step 2: Get required aspects for this category
print("\n2. Getting required aspects...")
response = requests.get(
    TAXONOMY_URL + '/category_tree/0/get_item_aspects_for_category',
    headers=get_headers(),
    params={'category_id': category_id}
)

required_aspects = {}
if response.status_code == 200:
    data = response.json()
    for aspect in data.get('aspects', []):
        constraint = aspect.get('aspectConstraint', {})
        if constraint.get('aspectRequired'):
            name = aspect.get('localizedAspectName')
            values = aspect.get('aspectValues', [])
            
            # Get first valid value
            if values:
                default = values[0].get('localizedValue')
            else:
                default = 'Other'
            
            # Special handling for MPN
            if name == 'MPN':
                default = 'Does Not Apply'
            
            required_aspects[name] = default
            print(f"   Required: {name} -> using '{default}'")

# Step 3: Create the listing
sku = 'TEST-' + uuid.uuid4().hex[:6].upper()
print("\n3. Creating inventory item:", sku)

# Build aspects - include all required ones
aspects = {}
for name, value in required_aspects.items():
    aspects[name] = [value]

# Always include brand
if 'Brand' not in aspects:
    aspects['Brand'] = ['Unbranded']

print("   Aspects:", aspects)

item = {
    'availability': {'shipToLocationAvailability': {'quantity': 1}},
    'condition': 'NEW',
    'product': {
        'title': 'TEST - Fiber Optic Cleaning Tool - Do Not Bid',
        'description': 'Test listing created via API. Do not bid.',
        'aspects': aspects
    }
}

response = requests.put(
    INVENTORY_URL + '/inventory_item/' + sku,
    headers=get_headers(),
    json=item
)
print("   Status:", response.status_code)
if response.status_code not in [200, 201, 204]:
    print("   Error:", response.text)
    exit(1)

# Step 4: Create offer
print("\n4. Creating offer...")
offer = {
    'sku': sku,
    'marketplaceId': 'EBAY_US',
    'format': 'FIXED_PRICE',
    'availableQuantity': 1,
    'categoryId': category_id,
    'listingDescription': 'Test listing created via API. Do not bid.',
    'listingPolicies': {
        'fulfillmentPolicyId': FULFILLMENT_POLICY,
        'paymentPolicyId': PAYMENT_POLICY,
        'returnPolicyId': RETURN_POLICY
    },
    'pricingSummary': {
        'price': {'value': '0.99', 'currency': 'USD'}
    },
    'merchantLocationKey': MERCHANT_LOCATION
}

response = requests.post(
    INVENTORY_URL + '/offer',
    headers=get_headers(),
    json=offer
)
print("   Status:", response.status_code)

if response.status_code not in [200, 201]:
    print("   Error:", response.text)
    exit(1)

offer_data = response.json()
offer_id = offer_data.get('offerId')
print("   Offer ID:", offer_id)

# Step 5: Publish
print("\n5. Publishing...")
response = requests.post(
    INVENTORY_URL + '/offer/' + offer_id + '/publish',
    headers=get_headers()
)
print("   Status:", response.status_code)

if response.status_code in [200, 201]:
    result = response.json()
    listing_id = result.get('listingId')
    print("\n" + "="*70)
    print("🎉 SUCCESS! LISTING PUBLISHED!")
    print("="*70)
    print("   Listing ID:", listing_id)
    print("   URL: https://www.ebay.com/itm/" + listing_id)
else:
    print("\n   Full error:")
    try:
        error = response.json()
        for e in error.get('errors', []):
            print("   -", e.get('message'))
            params = e.get('parameters', [])
            for p in params:
                print("     Param:", p.get('name'), "=", p.get('value'))
    except:
        print("   ", response.text[:500])
