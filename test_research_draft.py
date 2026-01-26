import sys
sys.path.insert(0, '.')
from create_research_draft import create_research_draft

images = [
    'C:/Users/adam/.gemini/antigravity/brain/140f97d9-c8ee-42e5-a405-1c19e6880663/uploaded_image_0_1769144758575.jpg',
    'C:/Users/adam/.gemini/antigravity/brain/140f97d9-c8ee-42e5-a405-1c19e6880663/uploaded_image_1_1769144758575.jpg'
]

print('Testing research-to-draft workflow on Xerox part...')
result = create_research_draft(images, auto_publish=False)

print()
print('FINAL RESULT:')
print('  Success:', result['success'])
print('  SKU:', result['sku'])
print('  Offer ID:', result['offer_id'])
print('  Item Specifics:', result['item_specifics_count'], 'fields')
if result.get('error'):
    print('  Error:', result['error'])
