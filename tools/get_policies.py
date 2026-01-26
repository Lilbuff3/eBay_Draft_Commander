"""
Get eBay Business Policies and create listing with them
"""
import json
import uuid
import requests
from pathlib import Path

def load_env():
    env_path = Path(__file__).parent / ".env"
    credentials = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                credentials[key.strip()] = value.strip()
    return credentials

credentials = load_env()
USER_TOKEN = credentials.get('EBAY_USER_TOKEN')

ACCOUNT_URL = 'https://api.ebay.com/sell/account/v1'
INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'

def get_headers():
    return {
        'Authorization': f'Bearer {USER_TOKEN}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

print("="*60)
print("Checking eBay Business Policies")
print("="*60)

# Get fulfillment (shipping) policies
print("\n📦 Fulfillment (Shipping) Policies:")
response = requests.get(f'{ACCOUNT_URL}/fulfillment_policy?marketplace_id=EBAY_US', headers=get_headers())
print(f"Status: {response.status_code}")

fulfillment_policy_id = None
if response.status_code == 200:
    data = response.json()
    policies = data.get('fulfillmentPolicies', [])
    if policies:
        for p in policies:
            print(f"  - {p.get('name')} (ID: {p.get('fulfillmentPolicyId')})")
            if not fulfillment_policy_id:
                fulfillment_policy_id = p.get('fulfillmentPolicyId')
    else:
        print("  No fulfillment policies found!")
else:
    print(f"Error: {response.text[:500]}")

# Get payment policies
print("\n💳 Payment Policies:")
response = requests.get(f'{ACCOUNT_URL}/payment_policy?marketplace_id=EBAY_US', headers=get_headers())
print(f"Status: {response.status_code}")

payment_policy_id = None
if response.status_code == 200:
    data = response.json()
    policies = data.get('paymentPolicies', [])
    if policies:
        for p in policies:
            print(f"  - {p.get('name')} (ID: {p.get('paymentPolicyId')})")
            if not payment_policy_id:
                payment_policy_id = p.get('paymentPolicyId')
    else:
        print("  No payment policies found!")
else:
    print(f"Error: {response.text[:500]}")

# Get return policies
print("\n🔄 Return Policies:")
response = requests.get(f'{ACCOUNT_URL}/return_policy?marketplace_id=EBAY_US', headers=get_headers())
print(f"Status: {response.status_code}")

return_policy_id = None
if response.status_code == 200:
    data = response.json()
    policies = data.get('returnPolicies', [])
    if policies:
        for p in policies:
            print(f"  - {p.get('name')} (ID: {p.get('returnPolicyId')})")
            if not return_policy_id:
                return_policy_id = p.get('returnPolicyId')
    else:
        print("  No return policies found!")
else:
    print(f"Error: {response.text[:500]}")

# Check inventory locations
print("\n📍 Inventory Locations:")
response = requests.get(f'{INVENTORY_URL}/location', headers=get_headers())
print(f"Status: {response.status_code}")

merchant_location_key = None
if response.status_code == 200:
    data = response.json()
    locations = data.get('locations', [])
    if locations:
        for loc in locations:
            print(f"  - {loc.get('name')} (Key: {loc.get('merchantLocationKey')})")
            if not merchant_location_key:
                merchant_location_key = loc.get('merchantLocationKey')
    else:
        print("  No inventory locations found!")
else:
    print(f"Error: {response.text[:500]}")

print("\n" + "="*60)
print("Summary")
print("="*60)
print(f"Fulfillment Policy: {fulfillment_policy_id}")
print(f"Payment Policy: {payment_policy_id}")
print(f"Return Policy: {return_policy_id}")
print(f"Merchant Location: {merchant_location_key}")

if all([fulfillment_policy_id, payment_policy_id, return_policy_id]):
    print("\n✅ All policies found! Ready to create listings.")
    
    # Save policy IDs to .env for later use
    with open(Path(__file__).parent / ".env", 'a') as f:
        f.write(f"\nEBAY_FULFILLMENT_POLICY={fulfillment_policy_id}")
        f.write(f"\nEBAY_PAYMENT_POLICY={payment_policy_id}")
        f.write(f"\nEBAY_RETURN_POLICY={return_policy_id}")
        if merchant_location_key:
            f.write(f"\nEBAY_MERCHANT_LOCATION={merchant_location_key}")
    print("✅ Policy IDs saved to .env")
    
else:
    print("\n⚠️ Missing policies! You need to set these up in eBay Seller Hub.")
    print("Go to: https://www.ebay.com/sh/settings/business-policies")
