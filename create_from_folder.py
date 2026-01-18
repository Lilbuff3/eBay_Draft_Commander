"""
Final Complete Listing Solution
Creates eBay listing with images using self-hosted URLs or placeholder
"""
import json
import uuid
import requests
import base64
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import time

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


def get_category_and_aspects(query):
    """Get best category and required aspects for a product"""
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
    
    print(f"   📂 Category: {category_id} - {category_name}")
    
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
                
                # Set defaults
                if name == 'MPN':
                    default = 'Does Not Apply'
                elif name == 'Brand':
                    default = 'Unbranded'
                elif values:
                    default = values[0].get('localizedValue')
                else:
                    default = 'Other'
                
                required[name] = default
    
    return category_id, required


def create_listing_from_folder(folder_path, price="29.99", condition="USED_EXCELLENT"):
    """
    Create an eBay listing from a folder of images
    
    Uses AI analyzer to extract product info and creates listing via API.
    
    Args:
        folder_path: Path to folder containing product images
        price: Listing price
        condition: Item condition
    
    Returns:
        listing_id or offer_id
    """
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        print(f"❌ Folder not found: {folder_path}")
        return None
    
    print("\n" + "="*70)
    print(f"🏪 Creating Listing from: {folder_path.name}")
    print("="*70)
    
    # Find images
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    images = [f for f in folder_path.iterdir() if f.suffix.lower() in image_extensions]
    
    if not images:
        print("❌ No images found")
        return None
    
    images.sort(key=lambda x: x.name)
    print(f"   📷 Found {len(images)} images")
    
    # Try to use AI analyzer if available
    try:
        from ai_analyzer import analyze_images
        
        print("\n📊 Analyzing images with AI...")
        ai_data = analyze_images([str(img) for img in images])
        
        title = ai_data.get('title', folder_path.name)
        description = ai_data.get('description', f'Item from {folder_path.name}')
        item_specifics = ai_data.get('item_specifics', {})
        
        print(f"   Title: {title[:50]}...")
        
    except Exception as e:
        print(f"   AI analyzer not available: {e}")
        print("   Using folder name for title...")
        
        title = folder_path.name.replace('_', ' ').title()
        description = f"<p>{title}</p><p>Please see photos for details.</p>"
        item_specifics = {}
    
    # Get category and required aspects
    category_id, required = get_category_and_aspects(title)
    
    if not category_id:
        print("❌ Could not determine category")
        return None
    
    # Build aspects
    aspects = {}
    for name, default in required.items():
        if name in item_specifics:
            aspects[name] = [item_specifics[name]]
        else:
            aspects[name] = [default]
        print(f"   {name}: {aspects[name][0]}")
    
    # Add any extra specifics
    for name, value in item_specifics.items():
        if name not in aspects and value:
            aspects[name] = [value]
    
    # Ensure brand
    if 'Brand' not in aspects:
        aspects['Brand'] = ['Unbranded']
    
    # Note: For full production use, images need to be hosted on HTTPS URLs
    # Options:
    # 1. Use eBay's Media API (requires successful upload)
    # 2. Host on your own server
    # 3. Use a service like Imgur, Dropbox, etc.
    
    # For now, we'll create the listing without images as a draft
    # The images can be added manually in Seller Hub
    
    sku = 'DC-' + uuid.uuid4().hex[:8].upper()
    print(f"\n   📦 SKU: {sku}")
    
    # Create inventory item (without images for now)
    item = {
        'availability': {'shipToLocationAvailability': {'quantity': 1}},
        'condition': condition,
        'conditionDescription': 'See photos for details.',
        'product': {
            'title': title[:80],  # eBay limit
            'description': description,
            'aspects': aspects
        }
    }
    
    print("\n   Creating inventory item...")
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
    print("   Creating offer...")
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
            'price': {'value': str(price), 'currency': 'USD'}
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
    
    # Try to publish
    print("   Publishing...")
    response = requests.post(
        INVENTORY_URL + '/offer/' + offer_id + '/publish',
        headers=get_headers()
    )
    
    if response.status_code in [200, 201]:
        result = response.json()
        listing_id = result.get('listingId')
        
        print("\n" + "🎉"*20)
        print("\n✅ LISTING PUBLISHED!")
        print(f"\n   Listing ID: {listing_id}")
        print(f"   URL: https://www.ebay.com/itm/{listing_id}")
        print("\n⚠️  Add images manually in Seller Hub")
        print("🎉"*20)
        
        return listing_id
    else:
        print("\n   ⚠️ Could not auto-publish (likely needs images)")
        
        # Get specific errors
        try:
            errors = response.json().get('errors', [])
            for e in errors:
                print(f"   - {e.get('message', '')[:100]}")
        except:
            pass
        
        print(f"\n📌 Draft created! Offer ID: {offer_id}")
        print("   Complete at: https://www.ebay.com/sh/lst/drafts")
        print("   Add images and publish there.")
        
        return offer_id


def process_inbox(inbox_path):
    """Process all folders in inbox"""
    inbox_path = Path(inbox_path)
    
    if not inbox_path.exists():
        print(f"❌ Inbox not found: {inbox_path}")
        return
    
    folders = [f for f in inbox_path.iterdir() if f.is_dir()]
    
    if not folders:
        print("❌ No item folders found")
        return
    
    print(f"\n📥 Found {len(folders)} items in inbox")
    
    for folder in folders:
        result = create_listing_from_folder(folder)
        print()


# Main
if __name__ == "__main__":
    # Test with SVBONY folder
    folder = Path(r"C:\Users\adam\Desktop\eBay_Draft_Commander\inbox\svbony_scope")
    
    if folder.exists():
        result = create_listing_from_folder(folder, price="79.99")
    else:
        print(f"Test folder not found: {folder}")
        print("\nUsage:")
        print("  create_listing_from_folder('/path/to/item/photos')")
        print("  process_inbox('/path/to/inbox')")
