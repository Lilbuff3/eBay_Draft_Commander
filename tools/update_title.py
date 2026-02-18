import sys
from pathlib import Path

sys.path.append("c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander")

from backend.app.services.ebay.inventory import InventoryService

def update_title(sku, new_title):
    print(f"🔄 Updating Title for SKU: {sku}")
    print(f"   New Title: {new_title}")
    
    service = InventoryService()
    
    # 1. Get existing item to preserve other fields
    item_resp, status = service.get_inventory_item(sku)
    if status != 200:
        print(f"❌ Could not fetch item: {status}")
        return

    # 2. Update Title
    item_resp['product']['title'] = new_title
    # Ensure description is synced too if desired, but title is key for SEO
    
    # 3. PUT update
    resp, code = service.create_inventory_item(sku, item_resp)
    
    if code in [200, 204]:
        print("✅ Title Updated Successfully!")
    else:
        print(f"❌ Update Failed ({code}): {resp}")

if __name__ == "__main__":
    sku = "DC-70A7ED27"
    new_title = "NOS NSPC West GX50-0001 Xenon Lamp for Xerox iGen3 iGen4 - DES80110A1"
    update_title(sku, new_title)
