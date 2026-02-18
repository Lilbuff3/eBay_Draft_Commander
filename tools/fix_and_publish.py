import requests
import json
import sys
from pathlib import Path

from backend.app.services.ebay.auth import eBayOAuth

def fix_and_publish(offer_id):
    print(f"🔧 Attempting to Fix Location and Publish Offer: {offer_id}...")
    
    oauth = eBayOAuth(use_sandbox=False)
    if not oauth.refresh_access_token():
        print("❌ Auth failed")
        return
    token = oauth.user_token
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Content-Language': 'en-US',
        'Accept': 'application/json'
    }
    
    # 1. Create NEW Location
    loc_key = "TEST-LOC-US"
    print(f"   Creating Location: {loc_key}...")
    location_data = {
        "name": "Test Location",
        "location": {
            "address": {
                "addressLine1": "123 Test St",
                "city": "San Jose",
                "stateOrProvince": "CA",
                "postalCode": "95125",
                "country": "US"
            }
        },
        "merchantLocationStatus": "ENABLED",
        "locationTypes": ["WAREHOUSE"]
    }
    
    resp = requests.post(f"https://api.ebay.com/sell/inventory/v1/location/{loc_key}", headers=headers, json=location_data)
    if resp.status_code not in [200, 204]:
        print(f"   ⚠️ Location creation warning: {resp.status_code} {resp.text}")
    else:
        print("   ✅ Location Created/Updated.")

    # 2. Get Offer Details to preserve other fields
    resp = requests.get(f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}", headers=headers)
    if resp.status_code != 200:
        print("❌ Failed to get offer")
        return
    offer_data = resp.json()
    
    # 3b. Fix Return Policy
    print("   Fetching Return Policies...")
    resp = requests.get(f"https://api.ebay.com/sell/account/v1/return_policy?marketplace_id=EBAY_US", headers=headers)
    if resp.status_code == 200:
        policies = resp.json().get('returnPolicies', [])
        valid_policy_id = None
        for p in policies:
            if p.get('name') and 'Return' in p.get('name'): # Heuristic match
                 valid_policy_id = p.get('returnPolicyId')
                 print(f"   Found Policy: {p.get('name')} ({valid_policy_id})")
                 break
        if not valid_policy_id and policies:
            valid_policy_id = policies[0].get('returnPolicyId') # Fallback to first
            
    # 3c. Fix Payment Policy
    print("   Fetching Payment Policies...")
    resp = requests.get(f"https://api.ebay.com/sell/account/v1/payment_policy?marketplace_id=EBAY_US", headers=headers)
    if resp.status_code == 200:
        policies = resp.json().get('paymentPolicies', [])
        valid_payment_id = policies[0].get('paymentPolicyId') if policies else None
        if valid_payment_id:
             print(f"   Updating Offer with Payment Policy: {valid_payment_id}")
             offer_data['listingPolicies']['paymentPolicyId'] = valid_payment_id

    # 3d. Fix Fulfillment Policy
    print("   Fetching Fulfillment Policies...")
    resp = requests.get(f"https://api.ebay.com/sell/account/v1/fulfillment_policy?marketplace_id=EBAY_US", headers=headers)
    if resp.status_code == 200:
        policies = resp.json().get('fulfillmentPolicies', [])
        valid_fulfillment_id = policies[0].get('fulfillmentPolicyId') if policies else None
        if valid_fulfillment_id:
             print(f"   Updating Offer with Fulfillment Policy: {valid_fulfillment_id}")
             offer_data['listingPolicies']['fulfillmentPolicyId'] = valid_fulfillment_id
             
    # Update Offer with ALL new policies
    resp = requests.put(f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}", headers=headers, json=offer_data)
    if resp.status_code in [200, 204]:
        print("   ✅ Offer Updated with ALL Valid Policies.")

    # 4. Try Publish
    print("   Attempting Publish...")
    resp = requests.post(f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish", headers=headers)
    if resp.status_code == 200:
        print("   🎉 SUCCESS! It Published!")
        print(f"   Listing ID: {resp.json().get('listingId')}")
    else:
        print(f"   ❌ Publish Failed: {resp.status_code}")
        try:
             # Print FULL Validation Errors
             errors = resp.json().get('errors', [])
             for e in errors:
                 print(f"   Error: {e.get('message')}")
                 if 'parameters' in e:
                     for p in e['parameters']:
                         print(f"     Param: {p.get('name')} = {p.get('value')}")
        except:
            pass

if __name__ == "__main__":
    fix_and_publish("110059367011")
