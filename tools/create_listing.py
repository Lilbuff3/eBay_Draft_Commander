"""
Create eBay Listing Directly - Full Demo
Uses the Inventory API to create a listing from your photos
"""
import json
import uuid
import requests
from pathlib import Path

# Load credentials
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

if not USER_TOKEN:
    print("❌ No user token found! Run exchange_token.py first.")
    exit(1)

print(f"✅ Loaded user token: {USER_TOKEN[:30]}...")

# API URLs
INVENTORY_URL = "https://api.ebay.com/sell/inventory/v1"

def get_headers():
    return {
        'Authorization': f'Bearer {USER_TOKEN}',
        'Content-Type': 'application/json',
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }

def create_inventory_location():
    """Create a merchant location (required for offers)"""
    url = f"{INVENTORY_URL}/location/DEFAULT"
    
    location_data = {
        "name": "Default Location",
        "location": {
            "address": {
                "city": "Your City",
                "stateOrProvince": "CA",
                "postalCode": "90210",
                "country": "US"
            }
        },
        "locationTypes": ["WAREHOUSE"],
        "merchantLocationStatus": "ENABLED"
    }
    
    response = requests.post(url, headers=get_headers(), json=location_data)
    print(f"Location creation: {response.status_code}")
    return response.status_code in [200, 201, 204]

def create_inventory_item(sku, listing_data):
    """Create an inventory item"""
    url = f"{INVENTORY_URL}/inventory_item/{sku}"
    
    # Build aspects (item specifics)
    aspects = {}
    item_specifics = listing_data.get('item_specifics', {})
    for key, value in item_specifics.items():
        if value:
            aspects[key] = [str(value)]
    
    item = {
        "availability": {
            "shipToLocationAvailability": {
                "quantity": 1
            }
        },
        "condition": "USED_EXCELLENT",
        "conditionDescription": "Item is in excellent used condition with minimal wear.",
        "product": {
            "title": listing_data.get('title', ''),
            "description": listing_data.get('description', ''),
            "aspects": aspects
        }
    }
    
    print(f"\n📦 Creating inventory item: {sku}")
    print(f"   Title: {listing_data.get('title', '')[:50]}...")
    
    response = requests.put(url, headers=get_headers(), json=item)
    
    print(f"   Response: {response.status_code}")
    if response.status_code not in [200, 201, 204]:
        print(f"   Error: {response.text[:500]}")
        return False
    
    print("   ✅ Inventory item created!")
    return True

def create_offer(sku, listing_data, category_id):
    """Create an offer (unpublished listing)"""
    url = f"{INVENTORY_URL}/offer"
    
    offer = {
        "sku": sku,
        "marketplaceId": "EBAY_US",
        "format": "FIXED_PRICE",
        "availableQuantity": 1,
        "categoryId": category_id,
        "listingDescription": listing_data.get('description', ''),
        "pricingSummary": {
            "price": {
                "value": str(listing_data.get('price', '50.00')),
                "currency": "USD"
            }
        },
        "merchantLocationKey": "DEFAULT"
    }
    
    print(f"\n📋 Creating offer...")
    print(f"   Category ID: {category_id}")
    print(f"   Price: ${listing_data.get('price', '50.00')}")
    
    response = requests.post(url, headers=get_headers(), json=offer)
    
    print(f"   Response: {response.status_code}")
    
    if response.status_code in [200, 201]:
        offer_data = response.json()
        offer_id = offer_data.get('offerId')
        print(f"   ✅ Offer created! ID: {offer_id}")
        return offer_id
    else:
        print(f"   Error: {response.text[:500]}")
        return None

def publish_offer(offer_id):
    """Publish an offer to create a live listing"""
    url = f"{INVENTORY_URL}/offer/{offer_id}/publish"
    
    print(f"\n🚀 Publishing offer {offer_id}...")
    
    response = requests.post(url, headers=get_headers())
    
    print(f"   Response: {response.status_code}")
    
    if response.status_code in [200, 201]:
        result = response.json()
        listing_id = result.get('listingId')
        print(f"   ✅ LISTING PUBLISHED!")
        print(f"   Listing ID: {listing_id}")
        print(f"   View at: https://www.ebay.com/itm/{listing_id}")
        return listing_id
    else:
        print(f"   Error: {response.text[:500]}")
        return None


def main():
    print("="*60)
    print("🏪 eBay Direct Listing Creator")
    print("="*60)
    
    # Load the SVBONY listing data
    listing_file = Path(__file__).parent / "svbony_listing.json"
    
    if not listing_file.exists():
        print("❌ No listing file found. Run the demo first!")
        return
    
    with open(listing_file, 'r') as f:
        listing_data = json.load(f)
    
    print(f"\n📄 Loaded listing: {listing_data.get('title', '')[:50]}...")
    
    # Generate unique SKU
    sku = f"DC-SVBONY-{uuid.uuid4().hex[:6].upper()}"
    print(f"   SKU: {sku}")
    
    # Step 1: Create inventory location (if needed)
    print("\n" + "-"*60)
    print("Step 1: Ensuring inventory location exists...")
    create_inventory_location()
    
    # Step 2: Create inventory item
    print("\n" + "-"*60)
    print("Step 2: Creating inventory item...")
    if not create_inventory_item(sku, listing_data):
        print("❌ Failed to create inventory item")
        return
    
    # Step 3: Create offer
    print("\n" + "-"*60)
    print("Step 3: Creating offer (draft listing)...")
    
    # Use the category ID from the listing data
    category_id = listing_data.get('category_id', '181951')
    offer_id = create_offer(sku, listing_data, category_id)
    
    if not offer_id:
        print("❌ Failed to create offer")
        return
    
    # Step 4: Ask about publishing
    print("\n" + "-"*60)
    print("Step 4: Publish listing?")
    print("\n⚠️  The offer is created as a DRAFT.")
    publish = input("Do you want to publish it now? (y/n): ").strip().lower()
    
    if publish == 'y':
        publish_offer(offer_id)
    else:
        print("\n📌 Draft saved! You can publish later from Seller Hub.")
    
    print("\n" + "="*60)
    print("✅ DONE!")
    print("="*60)


if __name__ == "__main__":
    main()
