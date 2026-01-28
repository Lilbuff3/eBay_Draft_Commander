"""
Debug: Check publish error in detail and find working category
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

INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'

def get_headers():
    return {
        'Authorization': 'Bearer ' + USER_TOKEN,
        'Content-Type': 'application/json',
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }

# Use a leaf category from the category tree
# 262336 = Toys & Hobbies > Models > Tools
category_id = "262336"

sku = 'TEST-' + uuid.uuid4().hex[:6].upper()
print("Testing with category", category_id)
print("SKU:", sku)

# Create minimal inventory item
item = {
    'availability': {'shipToLocationAvailability': {'quantity': 1}},
    'condition': 'NEW',
    'product': {
        'title': 'TEST LISTING - Do Not Bid - API Test',
        'description': 'Test listing. Do not bid.',
        'aspects': {
            'Brand': ['Unbranded']
        }
    }
}

print("\n1. Creating inventory item...")
response = requests.put(
    INVENTORY_URL + '/inventory_item/' + sku,
    headers=get_headers(),
    json=item
)
print("   Status:", response.status_code)
if response.status_code not in [200, 201, 204]:
    print("   Error:", response.text)
    exit(1)

# Create offer
print("\n2. Creating offer...")
offer = {
    'sku': sku,
    'marketplaceId': 'EBAY_US',
    'format': 'FIXED_PRICE',
    'availableQuantity': 1,
    'categoryId': category_id,
    'listingDescription': 'Test listing. Do not bid.',
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

# Get listing warnings (without publishing)
print("\n3. Getting listing fees (validates offer)...")
response = requests.post(
    INVENTORY_URL + '/offer/get_listing_fees',
    headers=get_headers(),
    json={'offers': [{'offerId': offer_id}]}
)
print("   Status:", response.status_code)
print("   Response:", json.dumps(response.json(), indent=2)[:1000])

# Try to publish
print("\n4. Attempting publish...")
response = requests.post(
    INVENTORY_URL + '/offer/' + offer_id + '/publish',
    headers=get_headers()
)
print("   Status:", response.status_code)
print("   Full response:", json.dumps(response.json(), indent=2) if response.text else "Empty")
