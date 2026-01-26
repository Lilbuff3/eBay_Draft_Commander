"""
eBay API Client for Draft Commander
Handles OAuth and Taxonomy API calls
"""
import os
import base64
import requests
from pathlib import Path

class eBayAPIClient:
    """Client for eBay REST APIs"""
    
    # API Endpoints
    AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    TAXONOMY_URL = "https://api.ebay.com/commerce/taxonomy/v1"
    
    # eBay US marketplace tree ID
    CATEGORY_TREE_ID = "0"  # US marketplace
    
    def __init__(self):
        """Initialize with credentials from .env file"""
        self.load_credentials()
        self.access_token = None
        
    def load_credentials(self):
        """Load API credentials from .env file"""
        env_path = Path(__file__).parent / ".env"
        
        if not env_path.exists():
            raise FileNotFoundError(f"No .env file found at {env_path}")
            
        credentials = {}
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()
        
        self.app_id = credentials.get('EBAY_APP_ID')
        self.dev_id = credentials.get('EBAY_DEV_ID')
        self.cert_id = credentials.get('EBAY_CERT_ID')
        
        if not all([self.app_id, self.cert_id]):
            raise ValueError("Missing required credentials in .env file")
            
        print(f"✅ Loaded credentials for: {self.app_id[:20]}...")
    
    def get_access_token(self):
        """Get OAuth access token using Client Credentials Grant"""
        if self.access_token:
            return self.access_token
            
        # Create Basic Auth header
        credentials = f"{self.app_id}:{self.cert_id}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }
        
        try:
            response = requests.post(self.AUTH_URL, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            print(f"✅ OAuth token obtained (expires in {token_data.get('expires_in', 'unknown')}s)")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get access token: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.text}")
            return None
    
    def get_category_suggestions(self, query):
        """
        Get category suggestions for a product query
        
        Args:
            query: Product name/description to search for
            
        Returns:
            List of category suggestions with IDs and paths
        """
        token = self.get_access_token()
        if not token:
            return []
            
        url = f"{self.TAXONOMY_URL}/category_tree/{self.CATEGORY_TREE_ID}/get_category_suggestions"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "q": query
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            suggestions = []
            
            for suggestion in data.get('categorySuggestions', []):
                category = suggestion.get('category', {})
                ancestors = suggestion.get('categoryTreeNodeAncestors', [])
                
                # Build full path
                path_parts = [a.get('categoryName', '') for a in reversed(ancestors)]
                path_parts.append(category.get('categoryName', ''))
                
                suggestions.append({
                    'category_id': category.get('categoryId'),
                    'category_name': category.get('categoryName'),
                    'full_path': ' > '.join(path_parts),
                    'relevancy': suggestion.get('relevancy', 0)
                })
            
            return suggestions
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get category suggestions: {e}")
            return []
    
    def get_item_aspects(self, category_id):
        """
        Get required and optional item aspects (specifics) for a category
        
        Args:
            category_id: eBay category ID
            
        Returns:
            Dict with required and optional aspects
        """
        token = self.get_access_token()
        if not token:
            return {'required': [], 'optional': []}
            
        url = f"{self.TAXONOMY_URL}/category_tree/{self.CATEGORY_TREE_ID}/get_item_aspects_for_category"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "category_id": category_id
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            required = []
            optional = []
            
            for aspect in data.get('aspects', []):
                aspect_info = {
                    'name': aspect.get('localizedAspectName'),
                    'data_type': aspect.get('aspectConstraint', {}).get('aspectDataType'),
                    'values': [v.get('localizedValue') for v in aspect.get('aspectValues', [])][:20],  # Limit values
                    'mode': aspect.get('aspectConstraint', {}).get('aspectMode'),
                    'required': aspect.get('aspectConstraint', {}).get('aspectRequired', False)
                }
                
                if aspect_info['required']:
                    required.append(aspect_info)
                else:
                    optional.append(aspect_info)
            
            return {
                'category_id': category_id,
                'required': required,
                'optional': optional[:10]  # Limit optional to top 10
            }
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get item aspects: {e}")
            return {'required': [], 'optional': []}


# Test the API client
if __name__ == "__main__":
    print("Testing eBay API Client...")
    
    client = eBayAPIClient()
    
    # Test category suggestions
    print("\n📦 Testing Category Suggestions...")
    suggestions = client.get_category_suggestions("fiber optic connector cleaner")
    
    for i, s in enumerate(suggestions[:5], 1):
        print(f"  {i}. {s['full_path']}")
        print(f"     ID: {s['category_id']}")
    
    # Test item aspects
    if suggestions:
        category_id = suggestions[0]['category_id']
        print(f"\n📋 Testing Item Aspects for category {category_id}...")
        aspects = client.get_item_aspects(category_id)
        
        print(f"  Required fields ({len(aspects['required'])}):")
        for a in aspects['required'][:5]:
            print(f"    - {a['name']}")
        
        print(f"  Optional fields ({len(aspects['optional'])}):")
        for a in aspects['optional'][:5]:
            print(f"    - {a['name']}")
