import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.ebay.inventory import InventoryService
from backend.app.services.ebay.policies import load_env

def publish_offer(offer_id):
    print(f"🚀 Publishing Offer ID: {offer_id}...")
    
    # Load Env
    load_env()
    service = InventoryService()
    
    try:
        response, status_code = service.publish_listing(offer_id)
        
        if status_code == 200:
            listing_id = response.get('listingId')
            print(f"\n✅ SUCCESS! Item is LIVE.")
            print(f"   Listing ID: {listing_id}")
            print(f"   URL: https://www.ebay.com/itm/{listing_id}")
            return True
        else:
            print(f"\n❌ FAILED (Status {status_code})")
            print(f"   Error: {response}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        offer_id = sys.argv[1]
        publish_offer(offer_id)
    else:
        print("Usage: python publish_offer.py <offer_id>")
