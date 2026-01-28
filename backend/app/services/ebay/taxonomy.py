"""
eBay Taxonomy Service
Handles category suggestions and item specifics metadata.
"""
import requests
from backend.app.services.ebay.policies import load_env, _get_headers

TAXONOMY_URL = "https://api.ebay.com/commerce/taxonomy/v1"

def get_suggested_category(query: str, limit: int = 1) -> dict:
    """
    Get suggested category for a query string.
    """
    if not query:
        return None
        
    try:
        url = f"{TAXONOMY_URL}/category_tree/0/get_category_suggestions"
        headers = _get_headers()
        params = {
            'q': query,
            'limit': limit
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            suggestions = data.get('categorySuggestions', [])
            if suggestions:
                # Return the primary category suggestion
                cat = suggestions[0].get('category', {})
                return {
                    'id': cat.get('categoryId'),
                    'name': cat.get('categoryName'),
                    'path': _format_category_path(suggestions[0].get('categoryTreeNodeAncestors', []))
                }
    except Exception as e:
        print(f"⚠️ Category suggestion failed: {e}")
        
    return None

def _format_category_path(ancestors: list) -> str:
    path = [a.get('categoryName') for a in ancestors]
    return " > ".join(path)
