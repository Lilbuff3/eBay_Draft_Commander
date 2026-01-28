import sys
import os
import json

# Add the project root to the python path
# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.ebay_service import eBayService
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_inventory():
    service = eBayService()
    print("Calling get_active_listings() [Hybrid Strategy]...")
    result, status = service.get_active_listings()
    
    if status == 200:
        count = result.get('total', 0)
        source = result.get('source', 'Unknown')
        print(f"✅ Success! Found {count} active listings.")
        print(f"📊 Source: {source}")
        
        # Print first item to verify structure
        items = result.get('listings', [])
        if items:
            print(f"First item:")
            print(json.dumps(items[0], indent=2))
    else:
        print(f"❌ Failed. Status: {status}")
        print(result)

if __name__ == "__main__":
    check_inventory()
