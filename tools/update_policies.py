import requests
import json
import sys
from pathlib import Path

from backend.app.services.ebay.auth import eBayOAuth

def update_env_policies():
    print("🔍 Fetching Valid Policies to update .env...")
    
    oauth = eBayOAuth(use_sandbox=False)
    if not oauth.refresh_access_token():
        print("❌ Auth failed")
        return
    token = oauth.user_token
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    policies_found = {}
    
    # Return Policy
    resp = requests.get(f"https://api.ebay.com/sell/account/v1/return_policy?marketplace_id=EBAY_US", headers=headers)
    if resp.status_code == 200:
        policies = resp.json().get('returnPolicies', [])
        for p in policies:
            if 'Return' in p.get('name', ''): 
                 policies_found['EBAY_RETURN_POLICY'] = p.get('returnPolicyId')
                 break
        if 'EBAY_RETURN_POLICY' not in policies_found and policies:
            policies_found['EBAY_RETURN_POLICY'] = policies[0].get('returnPolicyId')

    # Payment Policy
    resp = requests.get(f"https://api.ebay.com/sell/account/v1/payment_policy?marketplace_id=EBAY_US", headers=headers)
    if resp.status_code == 200:
        policies = resp.json().get('paymentPolicies', [])
        if policies:
            policies_found['EBAY_PAYMENT_POLICY'] = policies[0].get('paymentPolicyId')

    # Fulfillment Policy
    resp = requests.get(f"https://api.ebay.com/sell/account/v1/fulfillment_policy?marketplace_id=EBAY_US", headers=headers)
    if resp.status_code == 200:
         policies = resp.json().get('fulfillmentPolicies', [])
         if policies:
            policies_found['EBAY_FULFILLMENT_POLICY'] = policies[0].get('fulfillmentPolicyId')

    # Add Location Key
    policies_found['EBAY_MERCHANT_LOCATION'] = 'TEST-LOC-US'

    # Update .env
    env_path = Path('.env')
    if not env_path.exists():
        print("❌ .env not found")
        return

    lines = env_path.read_text().splitlines()
    new_lines = []
    updated_keys = set()
    
    for line in lines:
        key_match = False
        for key, value in policies_found.items():
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                updated_keys.add(key)
                key_match = True
                print(f"✅ Updated {key}={value}")
                break
        if not key_match:
            new_lines.append(line)
            
    # Append new keys if they didn't exist
    for key, value in policies_found.items():
        if key not in updated_keys:
             new_lines.append(f"{key}={value}")
             print(f"✅ Added {key}={value}")

    env_path.write_text('\n'.join(new_lines))
    print("\n🎉 .env updated successfully!")

if __name__ == "__main__":
    update_env_policies()
