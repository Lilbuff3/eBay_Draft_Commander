import sys
import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# Add project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

def get_user_id():
    token = os.getenv('EBAY_USER_TOKEN')
    if not token:
        print("No token found")
        return

    TRADING_URL = 'https://api.ebay.com/ws/api.dll'
    
    xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
    <GetUserRequest xmlns="urn:ebay:apis:eBLBaseComponents">
      <RequesterCredentials>
        <eBayAuthToken>{token}</eBayAuthToken>
      </RequesterCredentials>
      <DetailLevel>ReturnAll</DetailLevel>
    </GetUserRequest>"""
    
    headers = {
        'X-EBAY-API-SITEID': '0',
        'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
        'X-EBAY-API-CALL-NAME': 'GetUser',
        'Content-Type': 'text/xml'
    }

    print("Fetching User ID...")
    response = requests.post(TRADING_URL, headers=headers, data=xml_request)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return

    try:
        root = ET.fromstring(response.content)
        ns = {'e': 'urn:ebay:apis:eBLBaseComponents'}
        
        user = root.find('.//e:User', ns)
        if user is not None:
             user_id = user.find('e:UserID', ns).text
             print(f"✅ User ID: {user_id}")
             
             # Also check store URL if exists
             store = user.find('e:SellerInfo/e:StoreOwner', ns)
             print(f"Store Owner: {store.text if store is not None else 'No'}")
        else:
            print("Could not parse User ID from response")
            print(response.text[:500])
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    get_user_id()
