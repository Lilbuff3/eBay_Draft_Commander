
import requests
import os
from pathlib import Path
import json

def load_env():
    """Load environment variables"""
    # Adjust path to where .env is located (root of project)
    try:
        env_path = Path(r"c:\Users\adam\OneDrive\Documents\Desktop\Development\projects\ebay-draft-commander\.env")
        if not env_path.exists():
             # Try local if script is run from project root (fallback)
             env_path = Path(".env")
        
        credentials = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        credentials[key] = value
        return credentials
    except Exception as e:
        print(f"Error loading env: {e}")
        return {}

def get_headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Language': 'en-US',
        'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US',
    }

def test_get_offers():
    creds = load_env()
    token = creds.get('EBAY_USER_TOKEN')
    
    if not token:
        print("Error: EBAY_USER_TOKEN not found in .env")
        return

    url = "https://api.ebay.com/sell/inventory/v1/offer"
    params = {'limit': 10, 'offset': 0}
    
    print(f"Testing GET {url}...")
    try:
        response = requests.get(url, headers=get_headers(token), params=params)
        
        if response.status_code == 200:
            data = response.json()
            offers = data.get('offers', [])
            print(f"Success! Found {len(offers)} offers.")
            if offers:
                first = offers[0]
                print("\nSample Offer Data:")
                print(f"SKU: {first.get('sku')}")
                val = first.get('pricingSummary', {}).get('price', {}).get('value')
                print(f"Price: {val}")
                print(f"Status: {first.get('status')}")
                print(f"Avail: {first.get('availableQuantity')}")
                print(f"Title: {first.get('listing', {}).get('listingTitle', 'N/A')}")
        else:
            print(f"Failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Exception during request: {e}")

if __name__ == "__main__":
    test_get_offers()
