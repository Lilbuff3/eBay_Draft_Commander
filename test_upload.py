import requests
import sys
import shutil
from pathlib import Path

def upload_test():
    url = 'http://127.0.0.1:5000/api/upload'
    
    # Path to the artifact image
    image_path = Path(r"C:\Users\adam\.gemini\antigravity\brain\76b06f0d-8944-4557-94b5-b96ae5c6d2d4\test_product_photo_1769165547304.png")
    
    if not image_path.exists():
        print(f"❌ Image not found at {image_path}")
        return

    files = {
        'files[]': ('test_product_photo.png', open(image_path, 'rb'), 'image/png')
    }
    
    try:
        print(f"Uploading to {url}...")
        response = requests.post(url, files=files)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ Upload Successful!")
            print("Check your phone - a new job should appear in the queue.")
        else:
            print("\n❌ Upload Failed")
            
    except Exception as e:
        print(f"\n❌ Connection Error: {e}")
        print("Ensure backend is running (python backend/wsgi.py)")

if __name__ == '__main__':
    upload_test()
