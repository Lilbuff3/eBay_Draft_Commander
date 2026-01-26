"""
Live Demo: Analyze the SVBONY Spotting Scope
"""
import sys
sys.path.insert(0, r'C:\Users\adam\Desktop\eBay_Draft_Commander')
from ai_analyzer import AIAnalyzer
from ebay_api import eBayAPIClient
import json

print('='*70)
print('🔴 LIVE DEMO: Analyzing your SVBONY Spotting Scope photos')
print('='*70)

# Step 1: AI Analysis
print('\n📸 STEP 1: AI is looking at your 5 photos...')
print('-'*50)
analyzer = AIAnalyzer()
result = analyzer.analyze_folder(r'C:\Users\adam\Desktop\eBay_Draft_Commander\inbox\svbony_scope')

if 'error' not in result:
    print('✅ AI Analysis Complete!\n')
    
    # Show extracted data
    ident = result.get("identification", {})
    listing = result.get("listing", {})
    condition = result.get("condition", {})
    specs = result.get("specifications", {})
    
    print('📦 WHAT AI FOUND:')
    print(f'   Brand:     {ident.get("brand", "?")}')
    print(f'   Model:     {ident.get("model", "?")}')
    print(f'   Type:      {ident.get("product_type", "?")}')
    print(f'   Condition: {condition.get("state", "?")}')
    
    print('\n📝 GENERATED LISTING:')
    print(f'   Title: {listing.get("suggested_title", "?")}')
    print(f'   Price: ${listing.get("suggested_price", "?")}')
    
    print('\n📄 DESCRIPTION:')
    desc = listing.get("description", "")
    # Show first 500 chars
    print(f'   {desc[:500]}...' if len(desc) > 500 else f'   {desc}')
    
    # Step 2: eBay Categories
    print('\n' + '='*70)
    print('📂 STEP 2: Getting eBay Category Suggestions...')
    print('-'*50)
    
    api = eBayAPIClient()
    keywords = result.get('category_keywords', [listing.get('suggested_title', '')[:30]])
    query = ' '.join(keywords[:3]) if isinstance(keywords, list) else str(keywords)[:50]
    
    suggestions = api.get_category_suggestions(query)
    if suggestions:
        print('✅ eBay suggests these categories:')
        for i, s in enumerate(suggestions[:3], 1):
            print(f'   {i}. {s["full_path"]}')
    
    # Step 3: Required Fields
    print('\n' + '='*70)
    print('📋 STEP 3: Required Item Specifics for this category...')
    print('-'*50)
    
    if suggestions:
        aspects = api.get_item_aspects(suggestions[0]['category_id'])
        print(f'   Required fields: {[a["name"] for a in aspects["required"]]}')
        print(f'   Optional fields: {[a["name"] for a in aspects["optional"][:5]]}')
    
    # Step 4: Final Output
    print('\n' + '='*70)
    print('📄 STEP 4: FINAL LISTING DATA (Ready to copy!)')
    print('='*70)
    
    final_data = {
        'title': listing.get('suggested_title', ''),
        'price': listing.get('suggested_price', ''),
        'description': listing.get('description', ''),
        'category': suggestions[0]['full_path'] if suggestions else '',
        'item_specifics': {
            'Brand': ident.get('brand', ''),
            'Model': ident.get('model', ''),
            'MPN': ident.get('mpn', ''),
            'Type': ident.get('product_type', ''),
        }
    }
    
    print(json.dumps(final_data, indent=2))
    
    # Save it
    with open(r'C:\Users\adam\Desktop\eBay_Draft_Commander\svbony_listing.json', 'w') as f:
        json.dump(final_data, f, indent=2)
    print('\n✅ Saved to svbony_listing.json!')
    
else:
    print(f'❌ Error: {result.get("error")}')

print('\n' + '='*70)
print('🎉 DEMO COMPLETE! This is what the GUI does automatically.')
print('='*70)
