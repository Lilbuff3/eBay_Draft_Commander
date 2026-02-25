"""
eBay Taxonomy Service
Handles category suggestions and item specifics metadata.
"""
import requests
from backend.app.services.ebay.policies import load_env, _get_headers
from backend.app.core.logger import get_logger

logger = get_logger('ebay_taxonomy')

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
        logger.warning(f"Category suggestion failed: {e}")
        
    return None

def get_safe_category(title: str) -> dict:
    """
    Get category with 'Toner Trap' safety guard.
    Intercepts known hardware keywords and forces correct category.
    """
    title_lower = title.lower()
    
    # 1. HARDWARE KEYWORD GUARD
    # Corrected IDs after verification:
    # 51286 = Fusers
    # 51288 = Laser Drums
    # 170599 = Other Printer & Scanner Accs (Catch-all for belts, boards, etc)
    # 16204 = Toner Cartridges (AVOID THIS!)
    
    if "fuser" in title_lower:
        return {
            'id': '51286',
            'name': 'Fusers',
            'path': 'Computers/Tablets & Networking > Printers, Scanners & Supplies > Printer & Scanner Parts & Accs > Fusers',
            'source': 'guard_forced_fuser'
        }
        
    if "drum" in title_lower:
        return {
            'id': '51288',
            'name': 'Laser Drums',
            'path': 'Computers/Tablets & Networking > Printers, Scanners & Supplies > Printer & Scanner Parts & Accs > Laser Drums',
            'source': 'guard_forced_drum'
        }
    
    hardware_keywords = ['belt', 'sensor', 'motor', 'gear', 'board', 'roller', 'assembly', 'maintenance kit', 'panel', 'guide']
    if any(word in title_lower for word in hardware_keywords):
        return {
            'id': '170599',
            'name': 'Other Printer & Scanner Accs',
            'path': 'Computers/Tablets & Networking > Printers, Scanners & Supplies > Printer & Scanner Parts & Accs > Other Printer & Scanner Accs',
            'source': 'guard_forced_general'
        }
        
    # 2. QUERY INJECTION
    # If not caught by guard, try to steer the AI away from Toner by appending context
    search_query = title
    if "xerox" in title_lower and "toner" not in title_lower:
        search_query += " REPLACEMENT PART"
        
    suggestion = get_suggested_category(search_query)
    
    if suggestion:
        suggestion['source'] = 'ebay_api'
        
        # 3. SAFETY CHECK ON RESULT
        # If eBay STILL returned Toner (16201) but title doesn't say Toner, warn or override?
        # For now, let's trust the injection, but logging would happen in processor.
        
        return suggestion
        
    return None

def _format_category_path(ancestors: list) -> str:
    path = [a.get('categoryName') for a in ancestors]
    return " > ".join(path)

def get_category_suggestions(query: str) -> list:
    """
    Get a list of category suggestions for the E2E test and other consumers.
    """
    if not query:
        return []
        
    try:
        url = f"{TAXONOMY_URL}/category_tree/0/get_category_suggestions"
        headers = _get_headers()
        params = {'q': query}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            for sug in data.get('categorySuggestions', []):
                cat = sug.get('category', {})
                results.append({
                    'category_id': cat.get('categoryId'),
                    'category_name': cat.get('categoryName'),
                    'full_path': _format_category_path(sug.get('categoryTreeNodeAncestors', [])) + " > " + cat.get('categoryName')
                })
            return results
    except Exception as e:
        logger.warning(f"get_category_suggestions failed: {e}")
        
    return []

def get_item_aspects(category_id: str) -> dict:
    """
    Fetch required and optional item aspects for a given category.
    """
    if not category_id:
        return {"required": [], "optional": []}
        
    try:
        url = f"{TAXONOMY_URL}/category_tree/0/get_item_aspects_for_category"
        headers = _get_headers()
        params = {'category_id': category_id}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            aspects = data.get('aspects', [])
            
            required = []
            optional = []
            
            for a in aspects:
                aspect_info = {
                    "name": a.get('localizedAspectName'),
                    "usage": a.get('aspectUsage'),
                    "type": a.get('dataType'),
                    "values": [v.get('localizedValue') for v in a.get('relevantAspectValues', [])]
                }
                
                if a.get('aspectUsage') == 'REQUIRED':
                    required.append(aspect_info)
                else:
                    optional.append(aspect_info)
                    
            return {"required": required, "optional": optional}
    except Exception as e:
        logger.warning(f"get_item_aspects failed: {e}")
        
    return {"required": [], "optional": []}
