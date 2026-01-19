"""
eBay Policies API Module
Fetches fulfillment, payment, return policies and inventory locations.
"""
import requests
from pathlib import Path
from typing import Dict, List, Optional

ACCOUNT_URL = 'https://api.ebay.com/sell/account/v1'
INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'


def load_env():
    """Load credentials from .env file"""
    env_path = Path(__file__).parent / ".env"
    credentials = {}
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()
    return credentials


def _get_headers() -> Dict:
    """Get authorization headers with current token"""
    credentials = load_env()
    token = credentials.get('EBAY_USER_TOKEN')
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


def _refresh_token_if_needed(response) -> bool:
    """Refresh token if auth failed"""
    if response.status_code in [401, 500]:
        try:
            from ebay_auth import eBayOAuth
            oauth = eBayOAuth(use_sandbox=False)
            return oauth.refresh_access_token()
        except Exception:
            pass
    return False


def get_fulfillment_policies(retry: bool = True) -> List[Dict]:
    """
    Get all shipping/fulfillment policies.
    
    Returns:
        List of policy dicts with id, name, description
    """
    response = requests.get(
        f'{ACCOUNT_URL}/fulfillment_policy',
        headers=_get_headers(),
        params={'marketplace_id': 'EBAY_US'}
    )
    
    # Retry on auth failure
    if response.status_code in [401, 500] and retry:
        if _refresh_token_if_needed(response):
            return get_fulfillment_policies(retry=False)
    
    if response.status_code != 200:
        return []
    
    data = response.json()
    policies = []
    
    for p in data.get('fulfillmentPolicies', []):
        # Get shipping options description
        shipping_options = p.get('shippingOptions', [])
        shipping_desc = []
        for opt in shipping_options:
            carrier = opt.get('shippingCarrierCode', 'Various')
            service = opt.get('shippingServiceCode', '')
            cost_type = opt.get('costType', 'FLAT_RATE')
            
            if cost_type == 'CALCULATED':
                shipping_desc.append(f"{carrier}: Calculated")
            elif opt.get('freeShipping'):
                shipping_desc.append(f"{carrier}: FREE")
            else:
                shipping_desc.append(f"{carrier}: {service}")
        
        policies.append({
            'id': p.get('fulfillmentPolicyId'),
            'name': p.get('name'),
            'description': ' | '.join(shipping_desc) if shipping_desc else 'Standard shipping',
            'marketplace': p.get('marketplaceId'),
            'raw': p  # Include full policy for advanced use
        })
    
    return policies


def get_payment_policies(retry: bool = True) -> List[Dict]:
    """Get all payment policies"""
    response = requests.get(
        f'{ACCOUNT_URL}/payment_policy',
        headers=_get_headers(),
        params={'marketplace_id': 'EBAY_US'}
    )
    
    if response.status_code in [401, 500] and retry:
        if _refresh_token_if_needed(response):
            return get_payment_policies(retry=False)
    
    if response.status_code != 200:
        return []
    
    data = response.json()
    return [{
        'id': p.get('paymentPolicyId'),
        'name': p.get('name'),
        'description': p.get('description', 'Payment policy'),
        'marketplace': p.get('marketplaceId')
    } for p in data.get('paymentPolicies', [])]


def get_return_policies(retry: bool = True) -> List[Dict]:
    """Get all return policies"""
    response = requests.get(
        f'{ACCOUNT_URL}/return_policy',
        headers=_get_headers(),
        params={'marketplace_id': 'EBAY_US'}
    )
    
    if response.status_code in [401, 500] and retry:
        if _refresh_token_if_needed(response):
            return get_return_policies(retry=False)
    
    if response.status_code != 200:
        return []
    
    data = response.json()
    policies = []
    
    for p in data.get('returnPolicies', []):
        return_period = p.get('returnPeriod', {})
        period_value = return_period.get('value', 0)
        period_unit = return_period.get('unit', 'DAY')
        
        if p.get('returnsAccepted'):
            desc = f"{period_value} {period_unit.lower()}s returns"
        else:
            desc = "No returns"
        
        policies.append({
            'id': p.get('returnPolicyId'),
            'name': p.get('name'),
            'description': desc,
            'marketplace': p.get('marketplaceId')
        })
    
    return policies


def get_inventory_locations(retry: bool = True) -> List[Dict]:
    """Get all inventory/merchant locations"""
    response = requests.get(
        f'{INVENTORY_URL}/location',
        headers=_get_headers()
    )
    
    if response.status_code in [401, 500] and retry:
        if _refresh_token_if_needed(response):
            return get_inventory_locations(retry=False)
    
    if response.status_code != 200:
        return []
    
    data = response.json()
    return [{
        'id': loc.get('merchantLocationKey'),
        'name': loc.get('name'),
        'description': f"{loc.get('location', {}).get('address', {}).get('city', '')}, {loc.get('location', {}).get('address', {}).get('stateOrProvince', '')}",
        'enabled': loc.get('merchantLocationStatus') == 'ENABLED'
    } for loc in data.get('locations', [])]


def get_all_policies() -> Dict:
    """Get all policies in one call"""
    return {
        'fulfillment': get_fulfillment_policies(),
        'payment': get_payment_policies(),
        'return': get_return_policies(),
        'locations': get_inventory_locations()
    }


def get_current_defaults() -> Dict:
    """Get current default policy IDs from .env"""
    credentials = load_env()
    return {
        'fulfillment': credentials.get('EBAY_FULFILLMENT_POLICY'),
        'payment': credentials.get('EBAY_PAYMENT_POLICY'),
        'return': credentials.get('EBAY_RETURN_POLICY'),
        'location': credentials.get('EBAY_MERCHANT_LOCATION')
    }


# Test
if __name__ == "__main__":
    print("Testing eBay Policies API...")
    
    print("\n📦 Fulfillment Policies:")
    for p in get_fulfillment_policies():
        print(f"  - {p['name']} ({p['id'][:20]}...): {p['description']}")
    
    print("\n💳 Payment Policies:")
    for p in get_payment_policies():
        print(f"  - {p['name']} ({p['id'][:20]}...)")
    
    print("\n🔄 Return Policies:")
    for p in get_return_policies():
        print(f"  - {p['name']} ({p['id'][:20]}...): {p['description']}")
    
    print("\n📍 Locations:")
    for loc in get_inventory_locations():
        print(f"  - {loc['name']} ({loc['id']}): {loc['description']}")
    
    print("\n⚙️ Current Defaults:")
    defaults = get_current_defaults()
    for key, val in defaults.items():
        print(f"  - {key}: {val[:20] if val else 'Not set'}...")
