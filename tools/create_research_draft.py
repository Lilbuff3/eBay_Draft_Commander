"""
Research-to-Draft Creator for NOS/Industrial Equipment
Creates eBay drafts using search-grounded research and proper item specifics.
"""
import json
import uuid
import requests
from pathlib import Path
from typing import Dict, Optional, List


def load_env():
    """Load credentials from .env file"""
    env_path = Path(__file__).parent / ".env"
    credentials = {}
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()
    
    return credentials


credentials = load_env()
INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'
TAXONOMY_URL = 'https://api.ebay.com/commerce/taxonomy/v1'


def get_headers():
    """Get authorization headers"""
    token = credentials.get('EBAY_USER_TOKEN', '')
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Language': 'en-US'
    }


def refresh_token_if_needed():
    """Refresh token if expired"""
    try:
        from backend.app.services.ebay.auth import eBayOAuth
        auth = eBayOAuth()
        if not auth.has_valid_token():
            auth.refresh_access_token()
            # Reload credentials
            global credentials
            credentials = load_env()
    except Exception as e:
        print(f"⚠️ Token refresh check failed: {e}")

def get_category_for_item(research_data: Dict) -> tuple:
    """
    Get eBay category ID and required aspects from research data.
    
    Returns:
        (category_id, required_aspects_dict)
    """
    # Try to use the AI's category suggestion
    suggested_category = research_data.get('ebay_category_suggestion', '')
    keywords = research_data.get('category_keywords', [])
    
    # Build search query from identification
    ident = research_data.get('identification', {})
    query_parts = [
        ident.get('brand', ''),
        ident.get('product_type', ''),
        ident.get('mpn', '')
    ]
    query = ' '.join([p for p in query_parts if p])[:100]
    
    if not query:
        query = ' '.join(keywords[:3]) if keywords else 'industrial equipment'
    
    refresh_token_if_needed()
    
    # Get category suggestion from eBay Taxonomy API
    url = f"{TAXONOMY_URL}/category_tree/0/get_category_suggestions"
    params = {'q': query}
    
    try:
        response = requests.get(url, headers=get_headers(), params=params)
        if response.status_code == 200:
            data = response.json()
            suggestions = data.get('categorySuggestions', [])
            if suggestions:
                best = suggestions[0]
                category_id = best.get('category', {}).get('categoryId')
                
                # Get required aspects for this category
                aspects_url = f"{TAXONOMY_URL}/category_tree/0/get_item_aspects_for_category"
                aspects_response = requests.get(
                    aspects_url, 
                    headers=get_headers(),
                    params={'category_id': category_id}
                )
                
                required_aspects = {}
                if aspects_response.status_code == 200:
                    aspects_data = aspects_response.json()
                    for aspect in aspects_data.get('aspects', []):
                        if aspect.get('aspectConstraint', {}).get('aspectRequired'):
                            name = aspect.get('localizedAspectName')
                            # Get first recommended value as default
                            values = aspect.get('aspectValues', [])
                            default = values[0].get('localizedValue') if values else 'N/A'
                            required_aspects[name] = default
                
                return category_id, required_aspects
    except Exception as e:
        print(f"⚠️ Category lookup failed: {e}")
    
    return None, {}


def create_research_draft(
    image_paths: List[str],
    use_research: bool = True,
    auto_publish: bool = False,
    fulfillment_policy: str = None,
    payment_policy: str = None,
    return_policy: str = None,
    acquisition_cost: float = 0.0
) -> Dict:
    """
    Create an eBay draft listing from images using research-enhanced AI analysis.
    
    This is the main workflow for NOS/industrial equipment:
    1. Analyze images with AI
    2. Research part number via Google Search
    3. Map to eBay item specifics
    4. Smart Pricing check (comps + margin protection)
    5. Create inventory item + offer
    6. Optionally publish
    
    Args:
        image_paths: List of paths to product images
        use_research: Enable Google Search research (default True)
        auto_publish: Publish immediately (default False, creates draft)
        fulfillment_policy: eBay fulfillment policy ID
        payment_policy: eBay payment policy ID
        return_policy: eBay return policy ID
        acquisition_cost: Cost of goods sold (for margin protection)
        
    Returns:
        Dict with results including sku, offer_id, listing_id
    """
    result = {
        'success': False,
        'sku': None,
        'offer_id': None,
        'listing_id': None,
        'analysis_mode': None,
        'item_specifics_count': 0,
        'error': None
    }
    
    # Step 1: Analyze images with research
    print("=" * 60)
    print("RESEARCH-TO-DRAFT CREATOR")
    print("=" * 60)
    
    from backend.app.services.ai_analyzer import AIAnalyzer
    analyzer = AIAnalyzer()
    
    if use_research:
        analysis = analyzer.analyze_with_research(image_paths)
    else:
        analysis = analyzer.analyze_item(image_paths)
    
    if analysis.get('error'):
        result['error'] = analysis['error']
        return result
    
    result['analysis_mode'] = analysis.get('analysis_mode', 'basic')
    
    # Step 2: Extract data for listing
    ident = analysis.get('identification', {})
    listing = analysis.get('listing', {})
    condition_data = analysis.get('condition', {})
    
    # Use SEO-optimized title if available
    title = analysis.get('seo_title') or listing.get('suggested_title', 'Item for Sale')
    price = listing.get('suggested_price', '29.99')
    
    # Step 2a: Smart Pricing Check
    print(f"\n💲 SMART PRICING ANALYSIS (Cost: ${acquisition_cost:.2f})")
    try:
        from backend.app.services.pricing_engine import PricingEngine
        pricing_engine = PricingEngine()
        
        # Determine condition string
        cond_str = "Used - Good"
        if condition_data.get('is_nos'):
            cond_str = "New Old Stock"
        elif condition_data.get('state') == 'New':
            cond_str = "New"
            
        current_price_float = float(price) if price else 0.0
        
        price_result = pricing_engine.get_price_with_comps(
            title=title,
            condition=cond_str,
            ai_suggested_price=current_price_float,
            acquisition_cost=acquisition_cost
        )
        
        if price_result['suggested_price']:
            price = str(price_result['suggested_price'])
            profit = price_result.get('projected_profit')
            print(f"   ✅ Recommended Price: ${price}")
            if profit is not None:
                print(f"   📈 Projected Profit: ${profit:.2f}")
            print(f"   ℹ️  Reasoning: {price_result.get('reasoning')}")
        else:
            print("   ⚠️ Could not determine smart price, using AI estimate")
            
    except Exception as e:
        print(f"   ⚠️ Smart pricing failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Generate Professional HTML Description
    try:
        from backend.app.services.item_specifics_mapper import ItemSpecificsMapper
        mapper = ItemSpecificsMapper()
        description = mapper.generate_html_description(analysis)
        print("   ✅ Generated professional HTML template")
    except Exception as e:
        print(f"   ⚠️ HTML template generation failed: {e}")
        description = listing.get('description', '<p>See photos for details.</p>')
    
    # Get item specifics from mapper (already populated by analyze_with_research)
    item_specifics = analysis.get('item_specifics', {})
    result['item_specifics_count'] = len(item_specifics)
    
    # Get condition info
    condition_id = analysis.get('condition_id', 3000)  # Default to Used
    condition_desc = analysis.get('condition_description', 'See photos for details.')
    
    # Map condition ID to eBay condition enum
    condition_map = {
        1000: 'NEW',
        1500: 'NEW_OTHER',  # NOS
        2000: 'CERTIFIED_REFURBISHED',
        3000: 'USED_EXCELLENT',
        5000: 'USED_GOOD',
        6000: 'USED_ACCEPTABLE',
        7000: 'FOR_PARTS_OR_NOT_WORKING'
    }
    condition_enum = condition_map.get(condition_id, 'USED_EXCELLENT')
    
    print(f"\n📋 LISTING DATA")
    print(f"   Title: {title[:60]}...")
    print(f"   Price: ${price}")
    print(f"   Condition: {condition_enum} ({condition_id})")
    print(f"   Item Specifics: {len(item_specifics)} fields")
    
    for key, value in list(item_specifics.items())[:5]:
        print(f"      • {key}: {value}")
    if len(item_specifics) > 5:
        print(f"      ... and {len(item_specifics) - 5} more")
    
    # Step 3: Get category and required aspects
    print(f"\n🏷️ CATEGORY LOOKUP")
    category_id, required_aspects = get_category_for_item(analysis)
    
    if not category_id:
        result['error'] = 'Could not determine eBay category'
        return result
    
    print(f"   Category ID: {category_id}")
    print(f"   Required aspects: {len(required_aspects)}")
    
    # Build aspects dict (combine required + our specifics)
    aspects = {}
    
    # First, fill required aspects
    for name, default in required_aspects.items():
        if name in item_specifics:
            aspects[name] = [str(item_specifics[name])]
        else:
            aspects[name] = [default]
    
    # Then add all our item specifics
    for name, value in item_specifics.items():
        if name not in aspects:
            if isinstance(value, list):
                aspects[name] = value
            else:
                aspects[name] = [str(value)]
    
    print(f"   Total aspects: {len(aspects)}")
    
    # Step 4: Upload images
    print(f"\n📤 UPLOADING IMAGES")
    image_urls = []
    
    try:
        from backend.app.services.ebay.media import upload_images
        image_urls = upload_images(image_paths[:12])
        print(f"   ✅ Uploaded {len(image_urls)} images")
    except Exception as e:
        print(f"   ⚠️ Image upload failed: {e}")
        print("   Using placeholder image for draft")
        image_urls = ["https://placehold.co/800x600.png?text=Placeholder"]
    
    # Step 5: Create inventory item
    print(f"\n📦 CREATING INVENTORY ITEM")
    
    sku = 'NOS-' + uuid.uuid4().hex[:8].upper()
    result['sku'] = sku
    
    refresh_token_if_needed()
    
    inventory_item = {
        'availability': {
            'shipToLocationAvailability': {'quantity': 1}
        },
        'condition': condition_enum,
        'conditionDescription': condition_desc[:1000],
        'product': {
            'title': title[:80],
            'description': description[:500000],
            'aspects': aspects,
            'imageUrls': image_urls
        }
    }
    
    response = requests.put(
        f"{INVENTORY_URL}/inventory_item/{sku}",
        headers=get_headers(),
        json=inventory_item
    )
    
    if response.status_code not in [200, 201, 204]:
        error_msg = response.text[:500]
        print(f"   ❌ Error: {error_msg}")
        result['error'] = f"Inventory creation failed: {error_msg}"
        return result
    
    print(f"   ✅ Created inventory item: {sku}")
    
    # Step 6: Create offer
    print(f"\n💰 CREATING OFFER")
    
    # Get policy IDs
    fulfillment = fulfillment_policy or credentials.get('EBAY_FULFILLMENT_POLICY')
    payment = payment_policy or credentials.get('EBAY_PAYMENT_POLICY')
    returns = return_policy or credentials.get('EBAY_RETURN_POLICY')
    merchant_location = credentials.get('EBAY_MERCHANT_LOCATION')
    
    offer = {
        'sku': sku,
        'marketplaceId': 'EBAY_US',
        'format': 'FIXED_PRICE',
        'availableQuantity': 1,
        'categoryId': category_id,
        'listingDescription': description,
        'listingPolicies': {
            'fulfillmentPolicyId': fulfillment,
            'paymentPolicyId': payment,
            'returnPolicyId': returns
        },
        'pricingSummary': {
            'price': {'value': str(price), 'currency': 'USD'}
        }
    }
    
    if merchant_location:
        offer['merchantLocationKey'] = merchant_location
    
    response = requests.post(
        f"{INVENTORY_URL}/offer",
        headers=get_headers(),
        json=offer
    )
    
    if response.status_code not in [200, 201]:
        error_msg = response.text[:500]
        print(f"   ❌ Error: {error_msg}")
        result['error'] = f"Offer creation failed: {error_msg}"
        return result
    
    offer_data = response.json()
    offer_id = offer_data.get('offerId')
    result['offer_id'] = offer_id
    
    print(f"   ✅ Created offer: {offer_id}")
    
    # Step 7: Optionally publish
    if auto_publish and offer_id:
        print(f"\n🚀 PUBLISHING LISTING")
        
        publish_response = requests.post(
            f"{INVENTORY_URL}/offer/{offer_id}/publish",
            headers=get_headers()
        )
        
        if publish_response.status_code in [200, 201]:
            pub_data = publish_response.json()
            listing_id = pub_data.get('listingId')
            result['listing_id'] = listing_id
            print(f"   ✅ Published! Listing ID: {listing_id}")
        else:
            print(f"   ⚠️ Publish failed: {publish_response.text[:200]}")
            print("   Draft saved - publish manually from Seller Hub")
    else:
        print(f"\n📝 DRAFT CREATED (not published)")
        print(f"   View in Seller Hub > Listing > Drafts")
    
    result['success'] = True
    
    # Summary
    print(f"\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"   SKU: {result['sku']}")
    print(f"   Offer ID: {result['offer_id']}")
    print(f"   Listing ID: {result['listing_id'] or 'Draft (not published)'}")
    print(f"   Item Specifics: {result['item_specifics_count']} fields")
    print(f"   Analysis Mode: {result['analysis_mode']}")
    
    return result


# Test
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        folder = Path(sys.argv[1])
        if folder.is_dir():
            images = list(folder.glob('*.jpg')) + list(folder.glob('*.png'))
            images = [str(p) for p in images[:8]]
            print(f"Found {len(images)} images in {folder}")
            result = create_research_draft(images, auto_publish=False)
        else:
            print(f"Not a directory: {folder}")
    else:
        print("Usage: python create_research_draft.py /path/to/image/folder")
