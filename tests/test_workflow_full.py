
import os
import sys
from pathlib import Path
from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

from create_from_folder import create_listing_structured

print("="*60)
print("TEST: Full Listing Workflow")
print("="*60)

# 1. Setup Test Folder
test_folder = Path(r"inbox/test_job_1").absolute()
test_folder.mkdir(parents=True, exist_ok=True)

# Create dummy image if needed
img_path = test_folder / "test_image.jpg"
if not img_path.exists():
    print(f"Creating dummy image at {img_path}...")
    img = Image.new('RGB', (800, 800), color = 'red')
    img.save(img_path)

print(f"Targeted Folder: {test_folder}")

# 2. Run Creation
print("\nStarting creation process...")
result = create_listing_structured(test_folder, price="99.99", condition="USED_EXCELLENT")

# 3. Analyze Result
print("\n" + "-"*60)
print("RESULT ANALYSIS")
print("-" *60)
print(f"Success: {result.get('success')}")
print(f"Status:  {result.get('status')}")
print(f"Listing: {result.get('listing_id')}")
print(f"Offer:   {result.get('offer_id')}")

if result.get('error_message'):
    print(f"Error: {result.get('error_message')}")
else:
    print("Workflow successful!")

print("\nTiming:")
for k, v in result.get('timing', {}).items():
    print(f"   - {k}: {v:.2f}s")

print("="*60)
