"""
Get required aspects for category 31715
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

def get_headers():
    return {
        'Authorization': f'Bearer {USER_TOKEN}',
        'Accept': 'application/json'
    }

response = requests.get(
    'https://api.ebay.com/commerce/taxonomy/v1/category_tree/0/get_item_aspects_for_category',
    headers=get_headers(),
    params={'category_id': '31715'}
)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    
    print("\n" + "="*60)
    print("REQUIRED ASPECTS for category 31715:")
    print("="*60)
    
    for aspect in data.get('aspects', []):
        constraint = aspect.get('aspectConstraint', {})
        name = aspect.get('localizedAspectName')
        required = constraint.get('aspectRequired', False)
        
        if required:
            # Get value constraints
            values = aspect.get('aspectValues', [])
            value_names = [v.get('localizedValue') for v in values[:5]]
            
            print(f"\n► {name}")
            if value_names:
                print(f"  Example values: {', '.join(value_names[:5])}")
else:
    print(f"Error: {response.text}")
