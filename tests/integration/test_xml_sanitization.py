import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from backend.app.services.ebay.trading import TradingService

def test_xml_escaping():
    trading = TradingService()
    
    # A chaotic payload simulating a broken AI response with XML characters
    malicious_description = """
    <h2>Awesome Vintage Shirt</h2>
    <p>This shirt is > 10 years old & it's 100% authentic!</p>
    <div style="font-family: 'Arial';">"Perfect" Condition</div>
    And here is an accidental CDATA closure: ]]> Let's see if it breaks the payload.
    """
    
    item_data = {
        'title': "Test Shirt <Vintage & Retro> 100%",
        'description': malicious_description,
        'price': 25.50,
        'category_id': '175971', # Generic
        'condition_id': '3000', # Used
        'sku': 'TEST-XML-ESCAPE-001',
        'image_urls': ["https://i.ebayimg.com/images/g/test/s-l1600.jpg"],
        'item_specifics': {
            'Brand': 'Test Brand & Co.',
            'Size Type': 'Regular',
            'Size (Men\'s)': '"Large"'
        },
        'payment_policy_id': os.environ.get('EBAY_PAYMENT_POLICY'),
        'return_policy_id': os.environ.get('EBAY_RETURN_POLICY'),
        'fulfillment_policy_id': os.environ.get('EBAY_FULFILLMENT_POLICY'),
        'postal_code': '90210'
    }
    
    print("Testing AddFixedPriceItem with chaotic characters...")
    
    # Send it to eBay (Without scheduling, we'll just see if it parses)
    # Schedule it 14 days out so we don't accidentally post it live
    from datetime import datetime, timedelta, timezone
    schedule_time = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat().replace('+00:00', 'Z')
    
    result = trading.add_fixed_price_item(item_data, schedule_time=schedule_time)
    
    print("\nResult:")
    print(json.dumps(result, indent=2))
    
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    test_xml_escaping()
