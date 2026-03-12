import sys
import os
import json
import requests
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from backend.app.services.ebay.policies import _get_headers
from backend.config import Config

def test_create_item_draft():
    
    print("Getting REST token...")
    try:
        headers = _get_headers()
    except Exception as e:
        print(f"Failed to get REST headers: {e}")
        return
    
    # Adding specific headers required by eBay REST APIs
    headers["Content-Language"] = "en-US"
    headers["Accept"] = "application/json"
    headers["X-EBAY-C-MARKETPLACE-ID"] = "EBAY_US" 
    
    url = "https://api.ebay.com/sell/listing/v1_beta/item_draft"
    
    # Minimal payload required to create a draft
    # According to eBay docs, product is required.
    payload = {
        "product": {
            "title": "Test Item Please Ignore API Test",
            "description": "This is a test draft created via the Beta Listing API.",
            # Needs category
            "categoryId": "175971", # Generic category (e.g. Test Category if available, or just a random one)
            "imageUrls": [
                "https://i.ebayimg.com/images/g/test/s-l1600.jpg" # Dummy image
            ]
        },
        "condition": "NEW",
        "pricingSummary": {
            "price": {
                "value": "1.00",
                "currency": "USD"
            }
        }
    }
    
    print(f"Testing POST {url}")
    print("With payload:")
    print(json.dumps(payload, indent=2))
    print("-" * 50)
    
    response = requests.post(url, headers=headers, json=payload)
    
    print(f"Status Code: {response.status_code}")
    print("Response:")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)

if __name__ == "__main__":
    test_create_item_draft()
