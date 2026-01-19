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

# Token refresh helper
def refresh_token():
    """Refresh the eBay OAuth token and reload credentials"""
    global USER_TOKEN, credentials
    try:
        from ebay_auth import eBayOAuth
        print("   🔄 Refreshing eBay token...")
        oauth = eBayOAuth(use_sandbox=False)
        if oauth.refresh_access_token():
            # Reload the updated credentials
            credentials = load_env()
            USER_TOKEN = credentials.get('EBAY_USER_TOKEN')
            print("   ✅ Token refreshed!")
            return True
    except Exception as e:
        print(f"   ❌ Token refresh failed: {e}")
    return False


def get_headers():
    return {
        'Authorization': 'Bearer ' + USER_TOKEN,
        'Content-Type': 'application/json',
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }


def get_category_and_aspects(query, retry_on_auth=True):
    """Get best category and required aspects for a product"""
    # Get category
    response = requests.get(
        TAXONOMY_URL + '/category_tree/0/get_category_suggestions',
        headers=get_headers(),
        params={'q': query}
    )
    
    # Auto-refresh on auth errors
    if response.status_code in [401, 500] and retry_on_auth:
        if refresh_token():
            return get_category_and_aspects(query, retry_on_auth=False)
    
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


def create_listing_from_folder(folder_path, price="29.99", condition="USED_EXCELLENT", 
                                fulfillment_policy=None, payment_policy=None, return_policy=None):
    """
    Create an eBay listing from a folder of images
    
    Uses AI analyzer to extract product info and creates listing via API.
    
    Args:
        folder_path: Path to folder containing product images
        price: Listing price
        condition: Item condition
        fulfillment_policy: Optional fulfillment/shipping policy ID (uses default from .env if None)
        payment_policy: Optional payment policy ID (uses default from .env if None) 
        return_policy: Optional return policy ID (uses default from .env if None)
    
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
        from ai_analyzer import AIAnalyzer
        
        print("\n📊 Analyzing images with AI...")
        analyzer = AIAnalyzer()
        ai_data = analyzer.analyze_item([str(img) for img in images])
        
        title = ai_data.get('listing', {}).get('suggested_title', folder_path.name)
        description = ai_data.get('listing', {}).get('description', f'Item from {folder_path.name}')
        
        # Flatten structure for create_listing logic
        item_specifics = {}
        if 'identification' in ai_data:
            item_specifics.update(ai_data['identification'])
        if 'specifications' in ai_data:
            specs = ai_data['specifications']
            if isinstance(specs, dict):
                # Handle nested other_specs
                if 'other_specs' in specs:
                    other = specs.pop('other_specs')
                    if isinstance(other, dict):
                        for k, v in other.items():
                            if v and isinstance(v, (str, int, float)):
                                item_specifics[k] = str(v)
                
                # Add remaining simple specs
                for k, v in specs.items():
                    if v and isinstance(v, (str, int, float)):
                        item_specifics[k] = v
                    elif isinstance(v, list) and v:
                         item_specifics[k] = v[0] # Take first item of list
        
        if 'origin' in ai_data:
            if isinstance(ai_data['origin'], dict):
                item_specifics.update({k:v for k,v in ai_data['origin'].items() if isinstance(v, (str, int, float))})
            
        print(f"   Title: {title[:50]}...")
        
        # Get AI suggested price and condition for pricing engine
        ai_suggested_price = ai_data.get('listing', {}).get('suggested_price')
        condition_state = ai_data.get('condition', {}).get('state', 'Used - Good')
        
        # Call Pricing Engine
        try:
            from pricing_engine import PricingEngine
            pricing = PricingEngine()
            price_result = pricing.get_price_with_comps(
                title, 
                condition=condition_state,
                ai_suggested_price=ai_suggested_price
            )
            
            if price_result['suggested_price']:
                # Override with market-based or AI price
                final_price = str(price_result['suggested_price'])
                print(f"   💰 Price: ${final_price} ({price_result['source']})")
                if price_result.get('research_link'):
                    print(f"   🔗 Verify: {price_result['research_link']}")
            else:
                final_price = price  # Use default passed to function
        except Exception as e:
            print(f"   ⚠️ Pricing engine error: {e}")
            final_price = price  # Fallback to default
        
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
            if isinstance(value, (str, int, float)):
                 aspects[name] = [str(value)]
    
    # Ensure brand
    if 'Brand' not in aspects:
        aspects['Brand'] = ['Unbranded']
    
    # Note: For full production use, images need to be hosted on HTTPS URLs
    # Options:
    # 1. Use eBay's Media API (requires successful upload)
    # 2. Host on your own server
    # 3. Use a service like Imgur, Dropbox, etc.
    
    image_urls = []
    try:
        from ebay_media import upload_folder
        print(f"\n   📤 Uploading {len(images)} images to eBay Picture Services...")
        image_urls = upload_folder(folder_path, max_images=12)
        if image_urls:
            print(f"   ✅ Uploaded {len(image_urls)} images successfully")
        else:
            print("   ⚠️ Image upload failed or returned no URLs (will create listing without images)")
    except Exception as e:
        print(f"   ⚠️ Could not upload images: {e}")

    if not image_urls:
         print("   ⚠️ No images uploaded - using placeholder for draft creation")
         image_urls = ["https://placehold.co/800x600.png?text=Placeholder+Image"]

    sku = 'DC-' + uuid.uuid4().hex[:8].upper()
    print(f"\n   📦 SKU: {sku}")
    
    # Create inventory item
    item = {
        'availability': {'shipToLocationAvailability': {'quantity': 1}},
        'condition': condition,
        'conditionDescription': 'See photos for details.',
        'product': {
            'title': title[:80],  # eBay limit
            'description': description,
            'aspects': aspects,
            'imageUrls': image_urls
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
    
    # Use provided policies or fall back to defaults from .env
    actual_fulfillment = fulfillment_policy or FULFILLMENT_POLICY
    actual_payment = payment_policy or PAYMENT_POLICY
    actual_return = return_policy or RETURN_POLICY
    
    offer = {
        'sku': sku,
        'marketplaceId': 'EBAY_US',
        'format': 'FIXED_PRICE',
        'availableQuantity': 1,
        'categoryId': category_id,
        'listingDescription': description,
        'listingPolicies': {
            'fulfillmentPolicyId': actual_fulfillment,
            'paymentPolicyId': actual_payment,
            'returnPolicyId': actual_return
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
        if not image_urls:
            print("\n⚠️  Images were not uploaded. Add them in Seller Hub.")
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


# ============================================================================
# QUEUE INTEGRATION - Structured Results Wrapper
# ============================================================================

class ListingError(Exception):
    """Base exception for listing errors"""
    pass

class NoImagesError(ListingError):
    """No images found in folder"""
    pass

class AIAnalysisError(ListingError):
    """AI analysis failed"""
    pass

class CategoryError(ListingError):
    """Could not determine category"""
    pass

class ImageUploadError(ListingError):
    """Image upload failed"""
    pass

class InventoryError(ListingError):
    """Inventory item creation failed"""
    pass

class OfferError(ListingError):
    """Offer creation failed"""
    pass

class PublishError(ListingError):
    """Publishing failed"""
    pass


def create_listing_structured(folder_path, price="29.99", condition="USED_EXCELLENT"):
    """
    Queue-compatible wrapper for create_listing_from_folder.
    
    Returns structured result dict instead of just listing_id.
    
    Args:
        folder_path: Path to folder containing product images
        price: Listing price
        condition: Item condition
    
    Returns:
        dict with keys:
            success: bool
            listing_id: str or None
            offer_id: str or None
            status: "published" | "draft" | "error"
            error_type: str or None
            error_message: str or None
            timing: dict with timing info
    """
    import time
    start_time = time.time()
    timing = {}
    
    result = {
        "success": False,
        "listing_id": None,
        "offer_id": None,
        "status": "error",
        "error_type": None,
        "error_message": None,
        "timing": timing
    }
    
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        result["error_type"] = "FolderNotFound"
        result["error_message"] = f"Folder not found: {folder_path}"
        return result
    
    # Find images
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    images = [f for f in folder_path.iterdir() if f.suffix.lower() in image_extensions]
    
    if not images:
        result["error_type"] = "NoImages"
        result["error_message"] = "No images found in folder"
        return result
    
    images.sort(key=lambda x: x.name)
    
    # AI Analysis
    ai_start = time.time()
    try:
        from ai_analyzer import AIAnalyzer
        analyzer = AIAnalyzer()
        ai_data = analyzer.analyze_item([str(img) for img in images])
        
        title = ai_data.get('listing', {}).get('suggested_title', folder_path.name)
        description = ai_data.get('listing', {}).get('description', f'Item from {folder_path.name}')
        
        # Extract item specifics
        item_specifics = {}
        if 'identification' in ai_data:
            item_specifics.update(ai_data['identification'])
        if 'specifications' in ai_data:
            specs = ai_data['specifications']
            if isinstance(specs, dict):
                if 'other_specs' in specs:
                    other = specs.pop('other_specs')
                    if isinstance(other, dict):
                        for k, v in other.items():
                            if v and isinstance(v, (str, int, float)):
                                item_specifics[k] = str(v)
                for k, v in specs.items():
                    if v and isinstance(v, (str, int, float)):
                        item_specifics[k] = v
                    elif isinstance(v, list) and v:
                        item_specifics[k] = v[0]
        
        # Get AI pricing
        ai_suggested_price = ai_data.get('listing', {}).get('suggested_price')
        condition_state = ai_data.get('condition', {}).get('state', 'Used - Good')
        
        timing['ai_analysis'] = time.time() - ai_start
        
    except Exception as e:
        result["error_type"] = "AIAnalysis"
        result["error_message"] = str(e)
        timing['ai_analysis'] = time.time() - ai_start
        result["timing"] = timing
        return result
    
    # Pricing
    pricing_start = time.time()
    try:
        from pricing_engine import PricingEngine
        pricing = PricingEngine()
        price_result = pricing.get_price_with_comps(
            title, 
            condition=condition_state,
            ai_suggested_price=ai_suggested_price
        )
        if price_result['suggested_price']:
            final_price = str(price_result['suggested_price'])
        else:
            final_price = price
        timing['pricing'] = time.time() - pricing_start
    except Exception as e:
        final_price = price
        timing['pricing'] = time.time() - pricing_start
    
    # Category
    cat_start = time.time()
    try:
        category_id, required = get_category_and_aspects(title)
        if not category_id:
            raise CategoryError("Could not determine category")
        timing['category'] = time.time() - cat_start
    except Exception as e:
        result["error_type"] = "Category"
        result["error_message"] = str(e)
        result["timing"] = timing
        return result
    
    # Build aspects
    aspects = {}
    for name, default in required.items():
        if name in item_specifics:
            aspects[name] = [item_specifics[name]]
        else:
            aspects[name] = [default]
    for name, value in item_specifics.items():
        if name not in aspects and value:
            if isinstance(value, (str, int, float)):
                aspects[name] = [str(value)]
    if 'Brand' not in aspects:
        aspects['Brand'] = ['Unbranded']
    
    # Image upload
    upload_start = time.time()
    image_urls = []
    try:
        from ebay_media import upload_folder
        image_urls = upload_folder(folder_path, max_images=12)
        timing['image_upload'] = time.time() - upload_start
    except Exception as e:
        timing['image_upload'] = time.time() - upload_start
        # Non-fatal - continue without images

    if not image_urls:
         image_urls = ["https://placehold.co/800x600.png?text=Placeholder+Image"]
    
    # Create inventory item
    sku = 'DC-' + uuid.uuid4().hex[:8].upper()
    item = {
        'availability': {'shipToLocationAvailability': {'quantity': 1}},
        'condition': condition,
        'conditionDescription': 'See photos for details.',
        'product': {
            'title': title[:80],
            'description': description,
            'aspects': aspects,
            'imageUrls': image_urls
        }
    }
    
    api_start = time.time()
    try:
        response = requests.put(
            INVENTORY_URL + '/inventory_item/' + sku,
            headers=get_headers(),
            json=item
        )
        if response.status_code not in [200, 201, 204]:
            raise InventoryError(f"Inventory creation failed: {response.text[:200]}")
    except Exception as e:
        result["error_type"] = "Inventory"
        result["error_message"] = str(e)
        timing['api'] = time.time() - api_start
        result["timing"] = timing
        return result
    
    # Create offer
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
            'price': {'value': str(final_price), 'currency': 'USD'}
        },
        'merchantLocationKey': MERCHANT_LOCATION
    }
    
    try:
        response = requests.post(
            INVENTORY_URL + '/offer',
            headers=get_headers(),
            json=offer
        )
        if response.status_code not in [200, 201]:
            raise OfferError(f"Offer creation failed: {response.text[:200]}")
        
        offer_data = response.json()
        offer_id = offer_data.get('offerId')
        result["offer_id"] = offer_id
    except Exception as e:
        result["error_type"] = "Offer"
        result["error_message"] = str(e)
        timing['api'] = time.time() - api_start
        result["timing"] = timing
        return result
    
    # Try to publish
    try:
        response = requests.post(
            INVENTORY_URL + '/offer/' + offer_id + '/publish',
            headers=get_headers()
        )
        timing['api'] = time.time() - api_start
        
        if response.status_code in [200, 201]:
            publish_result = response.json()
            listing_id = publish_result.get('listingId')
            result["success"] = True
            result["listing_id"] = listing_id
            result["status"] = "published"
        else:
            # Could not publish but offer created (draft)
            result["success"] = True
            result["status"] = "draft"
    except Exception as e:
        # Offer exists, just couldn't publish
        result["success"] = True
        result["status"] = "draft"
    
    result["timing"] = timing
    result["timing"]["total"] = time.time() - start_time
    
    return result


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

