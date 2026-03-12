
import requests
import os
from pathlib import Path

def load_env():
    try:
        env_path = Path(r"c:\Users\adam\OneDrive\Documents\Desktop\Development\projects\ebay-draft-commander\.env")
        credentials = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        credentials[key] = value
        return credentials
    except:
        return {}

def test_trading_api():
    creds = load_env()
    token = creds.get('EBAY_USER_TOKEN')
    
    if not token:
        print("No token found")
        return

    url = "https://api.ebay.com/ws/api.dll"
    
    headers = {
        'X-EBAY-API-SITEID': '0',
        'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
        'X-EBAY-API-CALL-NAME': 'GetMyeBaySelling',
        'X-EBAY-API-IAF-TOKEN': token,
        'Content-Type': 'text/xml'
    }
    
    xml = """<?xml version="1.0" encoding="utf-8"?>
<GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <ActiveList>
    <Sort>TimeLeft</Sort>
    <Pagination>
      <EntriesPerPage>10</EntriesPerPage>
      <PageNumber>1</PageNumber>
    </Pagination>
  </ActiveList>
  <DetailLevel>ReturnAll</DetailLevel>
</GetMyeBaySellingRequest>"""

    print("Sending Trading API request...")
    resp = requests.post(url, headers=headers, data=xml)
    
    if resp.status_code == 200:
        print("Success! Response snippet:")
        print(resp.text[:1000])
        # Check for price in the XML
        if "CurrentPrice" in resp.text:
            print("\nFound CurrentPrice tags!")
        else:
            print("\nNo CurrentPrice tags found.")
    else:
        print(f"Failed: {resp.status_code}")
        print(resp.text)

if __name__ == "__main__":
    test_trading_api()
