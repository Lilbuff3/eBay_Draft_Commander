"""
Check and Publish eBay Offer
"""
import json
import requests
from pathlib import Path

def load_env():
    env_path = Path(__file__).parent / ".env"
    credentials = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                credentials[key.strip()] = value.strip()
    return credentials

credentials = load_env()
USER_TOKEN = credentials.get('EBAY_USER_TOKEN')

INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'

def get_headers():
    return {
        'Authorization': f'Bearer {USER_TOKEN}',
        'Content-Type': 'application/json',
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }

offer_id = '106128054011'

print(f"Checking offer {offer_id}...")

# Get offer details
response = requests.get(f'{INVENTORY_URL}/offer/{offer_id}', headers=get_headers())
print(f"Get Offer Status: {response.status_code}")

if response.status_code == 200:
    offer = response.json()
    print(f"Offer Status: {offer.get('status')}")
    print(f"Category: {offer.get('categoryId')}")
    print(f"SKU: {offer.get('sku')}")
    print(json.dumps(offer, indent=2)[:2000])

# Try to publish again
print("\nAttempting to publish...")
response = requests.post(f'{INVENTORY_URL}/offer/{offer_id}/publish', headers=get_headers())
print(f"Publish Status: {response.status_code}")
print(f"Response: {response.text}")
