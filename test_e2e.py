"""
End-to-End Test Script for eBay Draft Commander
"""
import sys
sys.path.insert(0, r'C:\Users\adam\Desktop\eBay_Draft_Commander')
from ai_analyzer import AIAnalyzer
from ebay_api import eBayAPIClient
import json

print('='*60)
print('END-TO-END TEST: eBay Draft Commander')
print('='*60)

# Step 1: AI Analysis
print('\n📸 STEP 1: AI Image Analysis')
print('-'*40)
analyzer = AIAnalyzer()
result = analyzer.analyze_folder(r'C:\Users\adam\Desktop\eBay_Draft_Commander\inbox\cletop_cleaner')

if 'error' in result:
    print(f'❌ AI Analysis failed: {result["error"]}')
else:
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
api = eBayAPIClient()
keywords = result.get('category_keywords', ['fiber optic connector cleaner'])
query = ' '.join(keywords[:3]) if keywords else 'fiber optic cleaner'
print(f'   Query: {query}')

suggestions = api.get_category_suggestions(query)
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
    aspects = api.get_item_aspects(cat_id)
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
with open(r'C:\Users\adam\Desktop\eBay_Draft_Commander\test_listing.json', 'w') as f:
    json.dump(listing_data, f, indent=2)
print('\n✅ Saved to test_listing.json')

print('\n' + '='*60)
print('END-TO-END TEST COMPLETE')
print('='*60)
