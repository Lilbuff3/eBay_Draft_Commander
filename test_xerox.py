import sys
sys.path.insert(0, '.')
from backend.app.services.ai_analyzer import AIAnalyzer
import json

analyzer = AIAnalyzer()
images = [
    'C:/Users/adam/.gemini/antigravity/brain/140f97d9-c8ee-42e5-a405-1c19e6880663/uploaded_image_0_1769144758575.jpg',
    'C:/Users/adam/.gemini/antigravity/brain/140f97d9-c8ee-42e5-a405-1c19e6880663/uploaded_image_1_1769144758575.jpg'
]
result = analyzer.analyze_with_research(images)

print('=== IDENTIFICATION ===')
ident = result.get('identification', {})
print(f"Brand: {ident.get('brand')}")
print(f"Model: {ident.get('model')}")
print(f"MPN: {ident.get('mpn')}")
print(f"Type: {ident.get('product_type')}")
print(f"Compatible: {ident.get('compatible_systems')}")

print()
print('=== CONDITION ===')
cond = result.get('condition', {})
print(f"State: {cond.get('state')}")
print(f"NOS: {cond.get('is_nos')}")
print(f"Sealed: {cond.get('factory_sealed')}")

print()
print('=== LISTING ===')
listing = result.get('listing', {})
print(f"Title: {listing.get('suggested_title')}")
print(f"Price: ${listing.get('suggested_price')}")
print(f"Reasoning: {listing.get('price_reasoning')}")

print()
print('=== RESEARCH ===')
research = result.get('research', {})
if research.get('researched'):
    print(f"Market Price: {research.get('market_price')}")
    print(f"Availability: {research.get('availability')}")
    print(f"Alt Part Numbers: {research.get('alternative_part_numbers')}")
else:
    print('No research data')

print()
print(f"Analysis Mode: {result.get('analysis_mode')}")

# Save full result
with open('xerox_test_result.json', 'w') as f:
    json.dump(result, f, indent=2)
print("Full result saved to xerox_test_result.json")
