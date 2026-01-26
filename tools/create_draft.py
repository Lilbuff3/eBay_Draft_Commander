import sys
import os
import argparse
import json
import time
from pathlib import Path

# Add project root to sys.path
root_path = Path(__file__).parent.parent
sys.path.insert(0, str(root_path))

from backend.app.services.ebay_service import eBayService
from backend.app.services.ebay.policies import get_payment_policies, get_return_policies, get_fulfillment_policies, get_inventory_locations
from backend.app.services.template_manager import get_template_manager

def create_draft(sku, title):
    print(f"--- B.L.A.S.T. Link Verification: Create Draft ---")
    
    # ... (Pre-checks skipped for brevity in diff, but kept in logic) ...
    service = eBayService()
    tm = get_template_manager()
    
    # 1. Connection Check
    print("\n[Step 1] Checking Connection...")
    status, code = service.check_connection_status()
    if status.get('status') != 'connected':
        print(f"[FAIL] {status}")
        return

    # Render HTML using the new Template System
    print("\n[Step 1.5] Rendering HTML Template...")
    aspects = {"Brand": ["B.L.A.S.T."], "Model": ["Verification Unit"], "Color": ["Test Blue"]}
    images = ["https://i.ebayimg.com/images/g/FwIAAOSw~jpj0~0~/s-l1600.jpg"]
    condition = "USED_EXCELLENT"
    
    html_description = tm.render_description(
        title=title,
        description="<p>This is a <strong>verified</strong> draft created with the new Mobile-First template system.</p>",
        images=images,
        aspects=aspects,
        condition="Used - Excellent Condition"
    )
    
    # 2. Create Inventory Item
    print("\n[Step 2] Creating Inventory Item (Product)...")
    item_data = {
        "sku": sku,
        "product": {
            "title": title,
            "description": f"Product: {title} - {condition}", # Short catalog description
            "aspects": aspects,
            "imageUrls": images
        },
        "condition": condition,
        "availability": {"shipToLocationAvailability": {"quantity": 1}}
    }
    
    resp, code = service.inventory_service.create_inventory_item(sku, item_data)
    if code not in [200, 204]:
        print(f"[FAIL] Item Create Failed")
        try:
             import json
             details = resp.get('details')
             if details:
                 err_obj = json.loads(details)
                 print(json.dumps(err_obj, indent=2))
             else:
                 print(resp)
        except:
             print(resp)
        return
    print("[OK] Inventory Item Created")
    
    print("  (Waiting 2s...)")
    time.sleep(2)

    # 3. Policies
    print("\n[Step 3] Fetching Policies...")
    payments = get_payment_policies()
    returns = get_return_policies()
    shipping = get_fulfillment_policies()
    locations = get_inventory_locations()
    
    if not payments or not returns or not shipping: return
    location_key = locations[0]['id'] if locations else "default"
    
    # 4. Create Offer
    print("\n[Step 4] Creating Offer...")
    offer_data = {
        "sku": sku,
        "marketplaceId": "EBAY_US",
        "format": "FIXED_PRICE",
        "listingDescription": html_description, # Same HTML
        "pricingSummary": {"price": {"value": "99.99", "currency": "USD"}},
        "listingPolicies": {
            "fulfillmentPolicyId": shipping[0]['id'],
            "paymentPolicyId": payments[0]['id'],
            "returnPolicyId": returns[0]['id']
        },
        "categoryId": "30093",
        "merchantLocationKey": location_key
    }
    
    resp, code = service.inventory_service.create_offer(offer_data)
    if code in [200, 201]:
        print(f"[SUCCESS] Draft Created! Offer ID: {resp.get('offerId')}")
    else:
        print(f"[FAIL] Offer Failed: {resp}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", default="BLAST-TEST-013")
    parser.add_argument("--title", default="BLAST Protocol Verification Item")
    args = parser.parse_args()
    
    create_draft(args.sku, args.title)
