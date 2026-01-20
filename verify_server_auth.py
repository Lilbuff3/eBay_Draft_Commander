import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

def test_auth_logic():
    print("Testing eBay Policies Auth Logic...")
    
    try:
        from ebay_policies import load_env, _get_headers, get_fulfillment_policies
        
        # 1. Check Env
        creds = load_env()
        print(f"Loaded credentials: {len(creds)} keys found")
        token = creds.get('EBAY_USER_TOKEN')
        print(f"Token present: {'Yes' if token else 'No'}")
        if token:
            print(f"Token preview: {token[:20]}...")
            
        # 2. Try an API call (Fulfillment Policies is a good read-only check)
        print("\nAttempting API Call (Get Fulfillment Policies)...")
        policies = get_fulfillment_policies(retry=True)
        
        if policies:
            print(f"SUCCESS: Fetched {len(policies)} policies")
            for p in policies[:3]:
                print(f" - {p['name']}")
        else:
            print("WARNING: API returned empty list (Auth might be okay, but no policies?)")
            
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_auth_logic()
