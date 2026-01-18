"""
Find the correct leaf category
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

credentials = load_env()
USER_TOKEN = credentials.get('EBAY_USER_TOKEN')

TAXONOMY_URL = 'https://api.ebay.com/commerce/taxonomy/v1'

def get_headers():
    return {
        'Authorization': f'Bearer {USER_TOKEN}',
        'Content-Type': 'application/json',
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }

# Get category suggestions for spotting scope
response = requests.get(
    f'{TAXONOMY_URL}/category_tree/0/get_category_suggestions',
    headers=get_headers(),
    params={'q': 'spotting scope 25-75x70'}
)

print(f"Status: {response.status_code}")
data = response.json()

for s in data.get('categorySuggestions', []):
    cat = s.get('category', {})
    cat_id = cat.get('categoryId')
    cat_name = cat.get('categoryName')
    
    ancestors = s.get('categoryTreeNodeAncestors', [])
    path_parts = [a.get('categoryName', '') for a in reversed(ancestors)]
    path_parts.append(cat_name)
    
    print(f"\nID: {cat_id}")
    print(f"Path: {' > '.join(path_parts)}")
    
    # Check if leaf
    is_leaf = s.get('category', {}).get('categoryTreeNodeLevel')
    print(f"Level: {is_leaf}")
