import sys
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def debug_xml():
    token = os.getenv('EBAY_USER_TOKEN')
    TRADING_URL = 'https://api.ebay.com/ws/api.dll'
    
    # 1. Match the exact date logic from ebay_service.py
    now = datetime.utcnow()
    future = now + timedelta(days=120)
    end_time_to = future.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    end_time_from = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    # 2. Match the exact XML request structure
    xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
    <GetSellerListRequest xmlns="urn:ebay:apis:eBLBaseComponents">
      <RequesterCredentials><eBayAuthToken>{token}</eBayAuthToken></RequesterCredentials>
      <EndTimeFrom>{end_time_from}</EndTimeFrom>
      <EndTimeTo>{end_time_to}</EndTimeTo>
      <Sort>2</Sort>
      <Pagination>
        <EntriesPerPage>200</EntriesPerPage>
        <PageNumber>1</PageNumber>
      </Pagination>
      <OutputSelector>PaginationResult</OutputSelector>
      <OutputSelector>ItemArray.Item.ItemID</OutputSelector>
      <OutputSelector>ItemArray.Item.Title</OutputSelector>
      <OutputSelector>ItemArray.Item.SKU</OutputSelector>
    </GetSellerListRequest>"""
    
    headers = {
        'X-EBAY-API-SITEID': '0',
        'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
        'X-EBAY-API-CALL-NAME': 'GetSellerList',
        'Content-Type': 'text/xml'
    }

    print(f"URL: {TRADING_URL}")
    print(f"Time Window: {end_time_from} to {end_time_to}")
    print("Sending request...")
    
    try:
        response = requests.post(TRADING_URL, headers=headers, data=xml_request, timeout=30)
        
        print(f"HTTP Status: {response.status_code}")
        print("--- Response Body Start ---")
        print(response.text[:2000] if response.text else "No content")
        print("--- Response Body End ---")
        
        if response.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            ns = {'e': 'urn:ebay:apis:eBLBaseComponents'}
            
            ack = root.find('.//e:Ack', ns)
            ack_text = ack.text if ack is not None else 'Unknown'
            print(f"eBay Ack: {ack_text}")
            
            errors = root.findall('.//e:Errors', ns)
            for err in errors:
                code = err.find('e:ErrorCode', ns).text
                short = err.find('e:ShortMessage', ns).text
                print(f"API Error: {code} - {short}")
                
            items = root.findall('.//e:Item', ns)
            print(f"Items found in XML: {len(items)}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug_xml()
