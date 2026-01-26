import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.ebay.inventory import InventoryService
from backend.app.services.ebay.policies import load_env

def check_offer(offer_id):
    print(f"🔍 Checking Offer ID: {offer_id}...")
    
    # Load Env to confirm context
    creds = load_env()
    print(f"   Context: {'SANDBOX' if 'SBX' in creds.get('EBAY_APP_ID', '') else 'PRODUCTION'}")
    
    service = InventoryService()
    
    try:
        response, status_code = service.get_offer(offer_id)
        
        if status_code == 200:
            print("\n✅ OFFER FOUND!")
            print(f"   Status: {response.get('status')}")
            print(f"   SKU: {response.get('sku')}")
            print(f"   Marketplace: {response.get('marketplaceId')}")
            print(f"   Category: {response.get('categoryId')}")
            print(f"   Available Qty: {response.get('availableQuantity')}")
            print(f"   Listing Description Length: {len(response.get('listingDescription', ''))}")
            
            if response.get('listingPolicies'):
                print(f"   Policies: {response.get('listingPolicies')}")
                
            # Fetch Product Details via SKU
            sku = response.get('sku')
            if sku:
                print(f"\n   Fetching details for SKU: {sku}...")
                item_response, item_status = service.get_inventory_item(sku)
                if item_status == 200:
                    product = item_response.get('product', {})
                    print(f"   📝 TITLE:  {product.get('title')}")
                    print(f"   📖 DESC:   {product.get('description')}")
                    print(f"   📸 IMAGES: {len(product.get('imageUrls', []))} attached")
                else:
                    print(f"   ⚠️ Could not fetch product details: {item_status}")

            # Check if it has a listingId (means it is published)
            listing_id = response.get('listingId')
            
            # Print Price
            pricing = response.get('pricingSummary', {}).get('price', {})
            print(f"   💰 PRICE: {pricing.get('value')} {pricing.get('currency')}")
            
            if listing_id:
                print(f"LISTING_ID:{listing_id}")
            else:
                print(f"STATUS:{response.get('status')}")
                # print(f"KEYS:{list(response.keys())}") # Reduce noise
                
        else:
            print(f"ERROR:{status_code}")
            print(f"   Response: {response}")
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        offer_id = sys.argv[1]
    else:
        offer_id = "109055391011" # Default to the reported one
        
    check_offer(offer_id)
