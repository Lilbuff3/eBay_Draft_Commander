import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add backend directory to sys.path so we can import app modules
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from backend.app.services.ebay_service import eBayService
from backend.app.services.ebay.policies import load_env

def test_scheduling():
    print("Testing eBay Listing Scheduling...")
    
    # Load env vars to make sure policies are available
    env_vars = load_env()
    
    # 1. Prepare Mock Item Data
    item_data = {
        'title': "White Ceramic Coffee Mug - Good Condition",
        'description': "<p>A generic white coffee mug. Great for coffee.</p>",
        'price': "9.99",
        'category_id': "170599", # Other Printer Parts (known valid leaf category)
        'condition_id': "3000", # Used
        'sku': "TEST-SCHED-01",
        'image_urls': ["https://i.ebayimg.com/images/g/cPIAAOSwyZxg18m-/s-l400.jpg"], # Provide one dummy image url
        'payment_policy_id': env_vars.get('EBAY_PAYMENT_POLICY'),
        'return_policy_id': env_vars.get('EBAY_RETURN_POLICY'),
        'fulfillment_policy_id': env_vars.get('EBAY_FULFILLMENT_POLICY'),
        'item_specifics': {
            'Brand': ['Unbranded'],
            'Type': ['Test Item']
        },
        'postal_code': env_vars.get('EBAY_POSTAL_CODE', '93611'),
        'item_location': 'Clovis, CA'
    }

    print("\nItem Data Payload Prepared:")
    print(f"- Title: {item_data['title']}")
    print(f"- Payment Policy: {item_data['payment_policy_id']}")
    print(f"- Return Policy: {item_data['return_policy_id']}")
    print(f"- Shipping Policy: {item_data['fulfillment_policy_id']}")

    # 2. Set Schedule Time (1 week from now, UTC ISO 8601)
    schedule_date = datetime.now(timezone.utc) + timedelta(days=7)
    schedule_time_str = schedule_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    print(f"\nScheduling for: {schedule_time_str}")

    # 3. Call Trading API Service
    print("\nExecuting AddFixedPriceItem via eBayService...")
    ebay = eBayService()
    result = ebay.create_trading_api_listing(item_data, schedule_time=schedule_time_str)
    
    # 4. Output Results
    print("\n--- TEST RESULTS ---")
    if result.get('success'):
        print(f"SUCCESS!")
        print(f"Listed Item ID: {result.get('item_id')}")
        print(f"Status: {result.get('status')} (Should be 'Scheduled')")
        print(f"Start Time: {result.get('start_time')}")
        print("\nNote: Please remember to delete this test listing from your active/scheduled eBay listings!")
    else:
        print(f"FAILED")
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    test_scheduling()
