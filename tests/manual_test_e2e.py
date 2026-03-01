"""
End-to-End Test Script for eBay Draft Commander
"""
import sys
from pathlib import Path

# Add current project directory to path
project_root = Path(__file__).parent.absolute()
project_parent = project_root.parent
sys.path.insert(0, str(project_parent))

from backend.app.services.ai_analyzer import AIAnalyzer
from backend.app.services.ebay_service import eBayService
import json

if __name__ == "__main__":
    print('='*60)
    print('END-TO-END TEST: eBay Draft Commander')
    print('='*60)

    # Step 1: AI Analysis
    print('\n📸 STEP 1: AI Image Analysis')
    print('-'*40)
    analyzer = AIAnalyzer()

    # Use images from inbox
    test_folder = project_parent / 'inbox' / 'web_upload_1772001574_d4d1'
    if not test_folder.exists():
        print(f'⚠️  Test folder not found: {test_folder}')
        sys.exit(1)

    # analyze_folder returns {'success': True, 'data': {...}}
    response = analyzer.analyze_folder(str(test_folder))
    print(f"RAW RESPONSE: {response}")
    
    if not isinstance(response, dict) or not response.get('success'):
        print(f'❌ AI Analysis failed: {response}')
        sys.exit(1)

    # Robust JSON extraction
    if isinstance(result, str):
        print(f"DEBUG: result is string, length {len(result)}")
        import re
        json_match = re.search(r'(\{.*\})', result, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                print("✅ Successfully extracted and parsed JSON from string")
            except Exception as e:
                print(f"❌ Failed to parse extracted JSON: {e}")
                sys.exit(1)
        else:
            print("❌ No JSON object found in result string")
            sys.exit(1)

    if not isinstance(result, dict):
        print(f"❌ Result is not a dictionary after parsing: {type(result)}")
        sys.exit(1)

    if 'error' in result:
        print(f'❌ AI Analysis error in result: {result["error"]}')
        sys.exit(1)
    
    print('✅ AI Analysis successful!')
    listing = result.get("listing", {})
    ident = result.get("identification", {})
    print(f'   Title: {listing.get("suggested_title", "N/A")}')
    print(f'   Price: ${listing.get("suggested_price", "N/A")}')
    print(f'   Brand: {ident.get("brand", "N/A")}')
    print(f'   MPN: {ident.get("mpn", "N/A")}')

    # Step 2: eBay API - Category Suggestions
    print('\n📂 STEP 2: eBay Category Suggestions')
    print('-'*40)
    from backend.app.services.ebay.taxonomy import get_category_suggestions, get_item_aspects
    # In the new structure, category_keywords might be deep in the result or identifying info
    keywords = ident.get('product_type', 'google pixel')
    query = ' '.join(keywords[:3]) if keywords else 'yonex'
    print(f'   Query: {query}')

    suggestions = get_category_suggestions(query)
    if suggestions:
        print('✅ Got category suggestions!')
        for i, s in enumerate(suggestions[:3], 1):
            print(f'   {i}. {s["full_path"]}')
            print(f'      ID: {s["category_id"]}')
    else:
        print('❌ No category suggestions returned')

    # Step 3: Item Aspects
    print('\n📋 STEP 3: Item Specifics (from eBay API)')
    print('-'*40)
    if suggestions:
        cat_id = suggestions[0]['category_id']
        aspects = get_item_aspects(cat_id)
        print(f'✅ Got item aspects for category {cat_id}')
        req_names = [a["name"] for a in aspects["required"]]
        opt_names = [a["name"] for a in aspects["optional"][:5]]
        print(f'   Required: {req_names}')
        print(f'   Optional: {opt_names}')

    # Step 4: Generate Final Listing Data
    print('\n📄 STEP 4: Final Listing Data (JSON)')
    print('-'*40)
    listing_data = {
        'title': result.get('listing', {}).get('suggested_title', ''),
        'price': result.get('listing', {}).get('suggested_price', ''),
        'description': result.get('listing', {}).get('description', ''),
        'category': suggestions[0]['full_path'] if suggestions else '',
        'category_id': suggestions[0]['category_id'] if suggestions else '',
        'item_specifics': {
            'Brand': result.get('identification', {}).get('brand', ''),
            'MPN': result.get('identification', {}).get('mpn', ''),
            'Model': result.get('identification', {}).get('model', ''),
            'Type': result.get('identification', {}).get('product_type', ''),
        }
    }
    print(json.dumps(listing_data, indent=2))

    # Save for browser test
    output_file = project_root / 'test_listing.json'
    with open(output_file, 'w') as f:
        json.dump(listing_data, f, indent=2)
    print(f'\n✅ Saved to {output_file.name}')

    print('\n' + '='*60)
    print('END-TO-END TEST COMPLETE')
    print('='*60)
