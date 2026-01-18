"""
Simple inventory check
"""
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

c = load_env()
token = c.get('EBAY_USER_TOKEN')

headers = {
    'Authorization': 'Bearer ' + token,
    'Accept': 'application/json'
}

# Get inventory items
print("Getting inventory items...")
r = requests.get('https://api.ebay.com/sell/inventory/v1/inventory_item', headers=headers, params={'limit': 20})
print('Status:', r.status_code)

if r.status_code == 200:
    data = r.json()
    total = data.get('total', 0)
    print('Total items:', total)
    
    for item in data.get('inventoryItems', []):
        sku = item.get('sku')
        title = item.get('product', {}).get('title', '')[:40]
        print('  SKU:', sku, '- Title:', title)
else:
    print('Error:', r.text[:300])
