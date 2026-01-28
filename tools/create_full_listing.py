"""
Create eBay Listing - Complete with Business Policies
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
        'Authorization': f'Bearer {USER_TOKEN}',
        'Content-Type': 'application/json',
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }

print("="*60)
print("🏪 Creating eBay Listing for SVBONY Spotting Scope")
print("="*60)

# Load the listing data
with open(Path(__file__).parent / 'svbony_listing.json') as f:
    listing_data = json.load(f)

sku = f'DC-SVBONY-{uuid.uuid4().hex[:6].upper()}'
print(f"SKU: {sku}")
print(f"Title: {listing_data.get('title', '')[:60]}...")

# Step 1: Create inventory item
print("\n📦 Step 1: Creating inventory item...")

aspects = {}
for key, value in listing_data.get('item_specifics', {}).items():
    if value:
        aspects[key] = [str(value)]

item = {
    'availability': {'shipToLocationAvailability': {'quantity': 1}},
    'condition': 'USED_EXCELLENT',
    'conditionDescription': 'Item is in excellent used condition with minimal wear.',
    'product': {
        'title': listing_data.get('title', ''),
        'description': listing_data.get('description', ''),
        'aspects': aspects
    }
}

response = requests.put(f'{INVENTORY_URL}/inventory_item/{sku}', headers=get_headers(), json=item)
print(f"   Response: {response.status_code}")
if response.status_code not in [200, 201, 204]:
    print(f"   Error: {response.text}")
    exit(1)
print("   ✅ Success!")

# Step 2: Create offer WITH business policies
print("\n📋 Step 2: Creating offer with business policies...")

offer = {
    'sku': sku,
    'marketplaceId': 'EBAY_US',
    'format': 'FIXED_PRICE',
    'availableQuantity': 1,
    'categoryId': '31710',  # Spotting Scopes
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

print(f"   Fulfillment Policy: {FULFILLMENT_POLICY}")
print(f"   Payment Policy: {PAYMENT_POLICY}")
print(f"   Return Policy: {RETURN_POLICY}")
print(f"   Location: {MERCHANT_LOCATION}")

response = requests.post(f'{INVENTORY_URL}/offer', headers=get_headers(), json=offer)
print(f"   Response: {response.status_code}")

if response.status_code not in [200, 201]:
    print(f"   Error: {response.text}")
    exit(1)

offer_data = response.json()
offer_id = offer_data.get('offerId')
print(f"   ✅ Offer created! ID: {offer_id}")

# Step 3: Publish the offer
print(f"\n🚀 Step 3: Publishing offer to create live listing...")

response = requests.post(f'{INVENTORY_URL}/offer/{offer_id}/publish', headers=get_headers())
print(f"   Response: {response.status_code}")

if response.status_code in [200, 201]:
    result = response.json()
    listing_id = result.get('listingId')
    print(f"\n" + "="*60)
    print("🎉 SUCCESS! LISTING PUBLISHED!")
    print("="*60)
    print(f"   Listing ID: {listing_id}")
    print(f"   View at: https://www.ebay.com/itm/{listing_id}")
else:
    print(f"   Error: {response.text}")
    print("\n📌 Offer created as DRAFT. Check Seller Hub to publish manually.")
    print(f"   Offer ID: {offer_id}")
