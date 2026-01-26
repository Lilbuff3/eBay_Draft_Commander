"""
eBay Direct Listing - Complete Solution
Properly fetches required aspects and publishes successfully
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

def get_best_category(query):
    """Get the best leaf category for a product"""
    response = requests.get(
        TAXONOMY_URL + '/category_tree/0/get_category_suggestions',
        headers=get_headers(),
        params={'q': query}
    )
    
    if response.status_code == 200:
        data = response.json()
        suggestions = data.get('categorySuggestions', [])
        if suggestions:
            return suggestions[0].get('category', {}).get('categoryId')
    return None

def get_required_aspects(category_id):
    """Get required aspects for a category"""
    response = requests.get(
        TAXONOMY_URL + '/category_tree/0/get_item_aspects_for_category',
        headers=get_headers(),
        params={'category_id': category_id}
    )
    
    required = {}
    if response.status_code == 200:
        data = response.json()
        for aspect in data.get('aspects', []):
            constraint = aspect.get('aspectConstraint', {})
            if constraint.get('aspectRequired'):
                name = aspect.get('localizedAspectName')
                values = aspect.get('aspectValues', [])
                
                # Get first valid value as default
                default_value = None
                if values:
                    default_value = values[0].get('localizedValue')
                
                required[name] = {
                    'required': True,
                    'default': default_value,
                    'values': [v.get('localizedValue') for v in values[:10]]
                }
    return required

def create_listing(title, description, price, item_specifics, category=None):
    """
    Create and publish a complete eBay listing
    
    Args:
        title: Listing title
        description: Item description
        price: Price as string (e.g., "79.99")
        item_specifics: Dict of item specifics (brand, model, etc.)
        category: Optional category ID (will auto-detect if not provided)
    
    Returns:
        listing_id if successful, None otherwise
    """
    
    print("\n" + "="*70)
    print("🏪 Creating eBay Listing")
    print("="*70)
    print("Title:", title[:60] + "...")
    
    # Step 1: Find category
    if not category:
        print("\n📂 Finding best category...")
        category = get_best_category(title)
        print("   Category ID:", category)
    
    # Step 2: Get required aspects
    print("\n📋 Checking required item specifics...")
    required = get_required_aspects(category)
    
    for name, info in required.items():
        print("   Required:", name)
        if name not in item_specifics:
            # Use default or first valid value
            if info.get('default'):
                item_specifics[name] = info['default']
                print("     -> Using default:", info['default'])
            else:
                print("     ⚠️ No value provided and no default!")
    
    # Step 3: Create inventory item
    sku = 'DC-' + uuid.uuid4().hex[:8].upper()
    print("\n📦 Creating inventory item...")
    print("   SKU:", sku)
    
    # Build aspects
    aspects = {}
    for key, value in item_specifics.items():
        if value:
            aspects[key] = [str(value)]
    
    item = {
        'availability': {'shipToLocationAvailability': {'quantity': 1}},
        'condition': 'USED_EXCELLENT',
        'conditionDescription': 'Item is in excellent used condition.',
        'product': {
            'title': title,
            'description': description,
            'aspects': aspects
        }
    }
    
    response = requests.put(
        INVENTORY_URL + '/inventory_item/' + sku,
        headers=get_headers(),
        json=item
    )
    
    if response.status_code not in [200, 201, 204]:
        print("   ❌ Failed:", response.text[:200])
        return None
    print("   ✅ Done!")
    
    # Step 4: Create offer
    print("\n📋 Creating offer...")
    
    offer = {
        'sku': sku,
        'marketplaceId': 'EBAY_US',
        'format': 'FIXED_PRICE',
        'availableQuantity': 1,
        'categoryId': category,
        'listingDescription': description,
        'listingPolicies': {
            'fulfillmentPolicyId': FULFILLMENT_POLICY,
            'paymentPolicyId': PAYMENT_POLICY,
            'returnPolicyId': RETURN_POLICY
        },
        'pricingSummary': {
            'price': {'value': price, 'currency': 'USD'}
        },
        'merchantLocationKey': MERCHANT_LOCATION
    }
    
    response = requests.post(
        INVENTORY_URL + '/offer',
        headers=get_headers(),
        json=offer
    )
    
    if response.status_code not in [200, 201]:
        print("   ❌ Failed:", response.text[:300])
        return None
    
    offer_data = response.json()
    offer_id = offer_data.get('offerId')
    print("   ✅ Offer ID:", offer_id)
    
    # Step 5: Publish
    print("\n🚀 Publishing...")
    
    response = requests.post(
        INVENTORY_URL + '/offer/' + offer_id + '/publish',
        headers=get_headers()
    )
    
    if response.status_code in [200, 201]:
        result = response.json()
        listing_id = result.get('listingId')
        
        print("\n" + "🎉" * 25)
        print("\n✅ SUCCESS! LISTING IS LIVE!")
        print("\n   Listing ID:", listing_id)
        print("   URL: https://www.ebay.com/itm/" + listing_id)
        print("\n" + "🎉" * 25)
        
        return listing_id
    else:
        error = response.json() if response.text else {}
        errors = error.get('errors', [])
        
        print("\n   ⚠️ Publish validation failed:")
        for e in errors:
            print("     -", e.get('message', str(e)))
        
        print("\n📌 Draft saved in your account.")
        print("   Complete it in Seller Hub: https://www.ebay.com/sh/lst/drafts")
        print("   Offer ID:", offer_id)
        
        return None


# Test with a simple item that doesn't require complex aspects
if __name__ == "__main__":
    # Create a simple test listing
    listing_id = create_listing(
        title="Test Listing - Electronics Item - Do Not Bid",
        description="This is a test listing created via the eBay Inventory API.",
        price="1.00",
        item_specifics={
            'Brand': 'Unbranded',
            'Type': 'Other'
        },
        category="293"  # Consumer Electronics - General
    )
    
    if listing_id:
        print("\n\nListing created successfully!")
    else:
        print("\n\nListing saved as draft.")
