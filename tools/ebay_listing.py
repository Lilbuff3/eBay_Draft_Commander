"""
eBay Listing Creator
Creates draft listings directly via the Inventory API
"""
import requests
import json
import uuid
from pathlib import Path

class eBayListingCreator:
    """Creates eBay listings via the Inventory API"""
    
    INVENTORY_URL = "https://api.ebay.com/sell/inventory/v1"
    
    def __init__(self):
        self.load_credentials()
        
    def load_credentials(self):
        """Load credentials including user token"""
        env_path = Path(__file__).parent / ".env"
        
        credentials = {}
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()
        
        self.user_token = credentials.get('EBAY_USER_TOKEN')
        
        if not self.user_token:
            raise ValueError("No EBAY_USER_TOKEN found. Run ebay_auth.py first!")
            
        print("✅ User token loaded")
    
    def get_headers(self):
        """Get headers with user authorization"""
        return {
            'Authorization': f'Bearer {self.user_token}',
            'Content-Type': 'application/json',
            'Content-Language': 'en-US',
            'Accept': 'application/json'
        }
    
    def create_inventory_item(self, sku, listing_data):
        """
        Create or update an inventory item
        
        Args:
            sku: Unique SKU for this item
            listing_data: Dict with title, description, price, category, item_specifics
        """
        url = f"{self.INVENTORY_URL}/inventory_item/{sku}"
        
        # Build the inventory item
        item = {
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": 1
                }
            },
            "condition": "USED_EXCELLENT",  # Default, can be customized
            "product": {
                "title": listing_data.get('title', ''),
                "description": listing_data.get('description', ''),
                "aspects": {},
                "imageUrls": listing_data.get('image_urls', [])
            }
        }
        
        # Add item specifics as aspects
        if listing_data.get('item_specifics'):
            for key, value in listing_data['item_specifics'].items():
                if value:
                    item['product']['aspects'][key] = [str(value)]
        
        try:
            response = requests.put(url, headers=self.get_headers(), json=item)
            
            if response.status_code in [200, 201, 204]:
                print(f"✅ Inventory item created: {sku}")
                return True
            else:
                print(f"❌ Failed to create inventory item: {response.status_code}")
                print(f"   {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error creating inventory item: {e}")
            return False
    
    def create_offer(self, sku, listing_data):
        """
        Create an offer (links inventory item to listing)
        
        Args:
            sku: SKU of the inventory item
            listing_data: Dict with price, category_id, etc.
        """
        url = f"{self.INVENTORY_URL}/offer"
        
        offer = {
            "sku": sku,
            "marketplaceId": "EBAY_US",
            "format": "FIXED_PRICE",
            "availableQuantity": 1,
            "categoryId": listing_data.get('category_id', ''),
            "listingDescription": listing_data.get('description', ''),
            "listingPolicies": {
                # These need to be set up in your eBay account
                # Or use the Account API to create them
            },
            "pricingSummary": {
                "price": {
                    "value": str(listing_data.get('price', '0.00')),
                    "currency": "USD"
                }
            },
            "merchantLocationKey": "default"  # Needs to be created first
        }
        
        try:
            response = requests.post(url, headers=self.get_headers(), json=offer)
            
            if response.status_code in [200, 201]:
                offer_data = response.json()
                offer_id = offer_data.get('offerId')
                print(f"✅ Offer created: {offer_id}")
                return offer_id
            else:
                print(f"❌ Failed to create offer: {response.status_code}")
                print(f"   {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating offer: {e}")
            return None
    
    def publish_offer(self, offer_id):
        """
        Publish an offer to create a live listing
        
        Args:
            offer_id: ID of the offer to publish
        """
        url = f"{self.INVENTORY_URL}/offer/{offer_id}/publish"
        
        try:
            response = requests.post(url, headers=self.get_headers())
            
            if response.status_code in [200, 201]:
                result = response.json()
                listing_id = result.get('listingId')
                print(f"✅ Listing published! ID: {listing_id}")
                print(f"   View at: https://www.ebay.com/itm/{listing_id}")
                return listing_id
            else:
                print(f"❌ Failed to publish: {response.status_code}")
                print(f"   {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error publishing: {e}")
            return None
    
    def create_draft_listing(self, listing_data):
        """
        Full workflow: Create inventory item + offer (draft)
        
        Args:
            listing_data: Complete listing data from Draft Commander
            
        Returns:
            offer_id if successful, None otherwise
        """
        # Generate unique SKU
        sku = f"DC-{uuid.uuid4().hex[:8].upper()}"
        
        print(f"\n📦 Creating draft listing...")
        print(f"   SKU: {sku}")
        print(f"   Title: {listing_data.get('title', '')[:50]}...")
        
        # Step 1: Create inventory item
        if not self.create_inventory_item(sku, listing_data):
            return None
        
        # Step 2: Create offer (draft)
        offer_id = self.create_offer(sku, listing_data)
        
        if offer_id:
            print(f"\n✅ Draft created successfully!")
            print(f"   Offer ID: {offer_id}")
            print(f"   SKU: {sku}")
            print(f"\n💡 To publish, call: creator.publish_offer('{offer_id}')")
            
        return offer_id
    
    def create_and_publish(self, listing_data):
        """
        Create and immediately publish a listing
        
        Args:
            listing_data: Complete listing data
            
        Returns:
            listing_id if successful, None otherwise
        """
        offer_id = self.create_draft_listing(listing_data)
        
        if offer_id:
            return self.publish_offer(offer_id)
        
        return None


# Test
if __name__ == "__main__":
    print("eBay Listing Creator Test")
    print("="*50)
    
    try:
        creator = eBayListingCreator()
        
        # Load the test listing
        test_file = Path(__file__).parent / "svbony_listing.json"
        
        if test_file.exists():
            with open(test_file, 'r') as f:
                listing_data = json.load(f)
            
            print(f"\nLoaded listing: {listing_data.get('title', '')[:50]}...")
            
            # Try to create draft
            offer_id = creator.create_draft_listing(listing_data)
            
            if offer_id:
                print("\n🎉 Success! Check your eBay Seller Hub for the draft.")
        else:
            print("No test listing found. Run demo.py first.")
            
    except ValueError as e:
        print(f"\n⚠️ {e}")
        print("\nRun the authorization first:")
        print("   python ebay_auth.py")
