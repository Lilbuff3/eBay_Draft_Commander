
from create_from_folder import create_listing_from_folder
import os

path = r"C:\Users\adam\Desktop\eBay_Draft_Commander\inbox\cletop_cleaner"
print(f"Running for: {path}")
try:
    create_listing_from_folder(path)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
