import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.ebay.inventory import InventoryService
from backend.app.services.ebay.policies import load_env

def end_listing(offer_id):
    print(f"🛑 Ending Offer ID: {offer_id}...")
    
    # Load Env
    load_env()
    service = InventoryService()
    
    try:
        # Get listing ID first
        resp, code = service.get_offer(offer_id)
        if code != 200:
            print(f"❌ Could not fetch offer: {code}")
            return
            
        listing_id = resp.get('listingId')
        status = resp.get('status', 'UNKNOWN')
        
        if not listing_id and status != 'PUBLISHED':
            print(f"⚠️ Offer is not published (Status: {status}).")
            return

        print(f"   Listing ID: {listing_id} (Status: {status})")
        
        # Withdraw offer (this ends the listing)
        print(f"   Calling withdraw_listing({offer_id})...")
        resp, code = service.withdraw_listing(offer_id)
        
        if code in [200, 204]:
             print(f"\n✅ SUCCESS! Listing Ended.")
        else:
             print(f"\n❌ FAILED to End (Status {code})")
             print(f"   Error: {resp}")

    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        offer_id = sys.argv[1]
        end_listing(offer_id)
    else:
        print("Usage: python end_listing.py <offer_id>")
