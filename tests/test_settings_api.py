import requests
import json

def test_settings_api():
    base_url = "http://127.0.0.1:5000/api/settings"
    
    print("Testing GET /api/settings...")
    try:
        response = requests.get(base_url)
        if response.status_code == 200:
            settings = response.json()
            print(f"✅ SUCCESS: Received {len(settings)} settings")
            print(f"Sample: EBAY_APP_ID = {settings.get('EBAY_APP_ID', 'NOT FOUND')}")
        else:
            print(f"❌ FAILED: Status code {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_settings_api()
