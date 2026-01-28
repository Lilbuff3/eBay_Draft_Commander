import sys
import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def debug_xml_title():
    token = os.getenv('EBAY_USER_TOKEN')
    TRADING_URL = 'https://api.ebay.com/ws/api.dll'
    
    now = datetime.utcnow()
    future = now + timedelta(days=120)
    end_time_to = future.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    end_time_from = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')

    # Reproduce the request that found 154 items but missing title
    xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
    <GetSellerListRequest xmlns="urn:ebay:apis:eBLBaseComponents">
      <RequesterCredentials><eBayAuthToken>{token}</eBayAuthToken></RequesterCredentials>
      <EndTimeFrom>{end_time_from}</EndTimeFrom>
      <EndTimeTo>{end_time_to}</EndTimeTo>
      <Sort>2</Sort>
      <Pagination>
        <EntriesPerPage>1</EntriesPerPage>
        <PageNumber>1</PageNumber>
      </Pagination>
      <OutputSelector>PaginationResult</OutputSelector>
      <OutputSelector>ItemArray.Item.ItemID</OutputSelector>
      <OutputSelector>ItemArray.Item.Title</OutputSelector>
    </GetSellerListRequest>"""
    
    headers = {
        'X-EBAY-API-SITEID': '0',
        'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
        'X-EBAY-API-CALL-NAME': 'GetSellerList',
        'Content-Type': 'text/xml'
    }

    print("Fetching 1 item with explicit selectors...")
    response = requests.post(TRADING_URL, headers=headers, data=xml_request)
    
    print(f"Status: {response.status_code}")
    # Print content
    print(response.content.decode('utf-8')[:2000])

if __name__ == "__main__":
    debug_xml_title()
