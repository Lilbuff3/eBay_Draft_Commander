"""
Complete eBay Listing Creator with Image Upload
Uses the modern Inventory API + Media API approach for 2026
"""
import json
import uuid
import requests
import base64
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
MEDIA_URL = 'https://api.ebay.com/commerce/media/v1_beta'

def get_headers():
    return {
        'Authorization': 'Bearer ' + USER_TOKEN,
        'Content-Type': 'application/json',
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }


def upload_image_from_url(image_url):
    """Upload an image to eBay Picture Services from a URL"""
    headers = {
        'Authorization': 'Bearer ' + USER_TOKEN,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    response = requests.post(
        MEDIA_URL + '/image',
        headers=headers,
        json={'url': image_url}
    )
    
    print(f"   Upload status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        data = response.json()
        return data.get('image', {}).get('imageUrl')
    else:
        print(f"   Upload error: {response.text[:200]}")
        return None


def get_category_and_aspects(query):
    """Get best category and required aspects"""
    # Get category
    response = requests.get(
        TAXONOMY_URL + '/category_tree/0/get_category_suggestions',
        headers=get_headers(),
        params={'q': query}
    )
    
    if response.status_code != 200:
        return None, {}
    
    data = response.json()
    suggestions = data.get('categorySuggestions', [])
    if not suggestions:
        return None, {}
    
    category_id = suggestions[0].get('category', {}).get('categoryId')
    category_name = suggestions[0].get('category', {}).get('categoryName')
    
    print(f"\n📂 Category: {category_id} - {category_name}")
    
    # Get required aspects
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
                
                # Get default value
                if name == 'MPN':
                    default = 'Does Not Apply'
                elif values:
                    default = values[0].get('localizedValue')
                else:
                    default = 'Other'
                
                required[name] = default
    
    return category_id, required


def create_ebay_listing(title, description, price, image_urls, item_specifics=None):
    """
    Create a complete eBay listing with images
    
    Args:
        title: Listing title
        description: Item description
        price: Price as string (e.g., "79.99")
        image_urls: List of HTTPS image URLs
        item_specifics: Optional dict of item specifics
    
    Returns:
        listing_id if successful, offer_id if draft, None if failed
    """
    
    print("\n" + "="*70)
    print("🏪 eBay Direct Listing Creator")
    print("="*70)
    print(f"Title: {title[:60]}...")
    print(f"Price: ${price}")
    print(f"Images: {len(image_urls)}")
    
    # Get category and aspects
    category_id, required_aspects = get_category_and_aspects(title)
    
    if not category_id:
        print("❌ Could not find category")
        return None
    
    # Merge item specifics with defaults
    aspects = {}
    for name, default in required_aspects.items():
        if item_specifics and name in item_specifics:
            aspects[name] = [item_specifics[name]]
        else:
            aspects[name] = [default]
        print(f"   {name}: {aspects[name][0]}")
    
    # Add any extra item specifics
    if item_specifics:
        for name, value in item_specifics.items():
            if name not in aspects:
                aspects[name] = [value]
    
    # Always include brand
    if 'Brand' not in aspects:
        aspects['Brand'] = ['Unbranded']
    
    # Create SKU
    sku = 'DC-' + uuid.uuid4().hex[:8].upper()
    print(f"\n📦 SKU: {sku}")
    
    # Create inventory item
    print("\n📦 Creating inventory item...")
    
    item = {
        'availability': {'shipToLocationAvailability': {'quantity': 1}},
        'condition': 'USED_EXCELLENT',
        'conditionDescription': 'Item is in excellent used condition.',
        'product': {
            'title': title,
            'description': description,
            'aspects': aspects,
            'imageUrls': image_urls[:12]  # eBay max 12 images
        }
    }
    
    response = requests.put(
        INVENTORY_URL + '/inventory_item/' + sku,
        headers=get_headers(),
        json=item
    )
    
    if response.status_code not in [200, 201, 204]:
        print(f"   ❌ Error: {response.text[:300]}")
        return None
    print("   ✅ Done!")
    
    # Create offer
    print("\n📋 Creating offer...")
    
    offer = {
        'sku': sku,
        'marketplaceId': 'EBAY_US',
        'format': 'FIXED_PRICE',
        'availableQuantity': 1,
        'categoryId': category_id,
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
        print(f"   ❌ Error: {response.text[:300]}")
        return None
    
    offer_data = response.json()
    offer_id = offer_data.get('offerId')
    print(f"   ✅ Offer ID: {offer_id}")
    
    # Publish
    print("\n🚀 Publishing...")
    
    response = requests.post(
        INVENTORY_URL + '/offer/' + offer_id + '/publish',
        headers=get_headers()
    )
    
    if response.status_code in [200, 201]:
        result = response.json()
        listing_id = result.get('listingId')
        
        print("\n" + "🎉"*25)
        print("\n✅ LISTING PUBLISHED SUCCESSFULLY!")
        print(f"\n   Listing ID: {listing_id}")
        print(f"   URL: https://www.ebay.com/itm/{listing_id}")
        print("\n" + "🎉"*25)
        
        return listing_id
    else:
        print("\n   ⚠️ Could not publish automatically.")
        try:
            error = response.json()
            for e in error.get('errors', []):
                print(f"   - {e.get('message')}")
        except:
            pass
        
        print(f"\n📌 Draft saved! Offer ID: {offer_id}")
        print("   Complete at: https://www.ebay.com/sh/lst/drafts")
        
        return offer_id


# Example usage
if __name__ == "__main__":
    # Example with SVBONY spotting scope - using placeholder image URLs
    # In real use, these would be actual HTTPS URLs to product images
    
    image_urls = [
        "https://i.ebayimg.com/images/g/placeholder.jpg"  # Replace with real URLs
    ]
    
    result = create_ebay_listing(
        title="SVBONY SV28 25-75x70 Spotting Scope Waterproof with Phone Adapter",
        description="""
        <h2>SVBONY SV28 Spotting Scope</h2>
        <p>25-75x zoom magnification with 70mm objective lens.</p>
        <ul>
            <li>Waterproof construction</li>
            <li>Includes phone adapter</li>
            <li>Excellent for birdwatching and nature observation</li>
        </ul>
        """,
        price="79.99",
        image_urls=image_urls,
        item_specifics={
            'Brand': 'SVBONY',
            'Model': 'SV28',
            'Type': 'Spotting Scope',
            'MPN': 'SV28'
        }
    )
    
    if result:
        print(f"\n\n✅ Process complete: {result}")
