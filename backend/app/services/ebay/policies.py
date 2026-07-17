"""
eBay Policies API Module
Fetches fulfillment, payment, return policies and inventory locations.
"""
import requests
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
from backend.app.core.logger import get_logger
from backend.app.core.rate_limiter import limiter

logger = get_logger('ebay_policies')

ACCOUNT_URL = 'https://api.ebay.com/sell/account/v1'
INVENTORY_URL = 'https://api.ebay.com/sell/inventory/v1'


from dotenv import load_dotenv, find_dotenv

def load_env():
    """Load credentials from .env file using python-dotenv"""
    env_path = find_dotenv()
    if env_path:
        load_dotenv(env_path)
    
    # Return a dict for compatibility with existing code
    return {key: os.environ.get(key) for key in [
        'EBAY_APP_ID', 'EBAY_CERT_ID', 'EBAY_DEV_ID', 'EBAY_RU_NAME',
        'EBAY_USER_TOKEN', 'EBAY_REFRESH_TOKEN', 'EBAY_USER_ACCESS_TOKEN',
        'EBAY_FULFILLMENT_POLICY', 'EBAY_PAYMENT_POLICY', 'EBAY_RETURN_POLICY',
        'EBAY_MERCHANT_LOCATION'
    ]}


def _get_headers() -> Dict:
    """Get authorization headers with current token"""
    from backend.app.core.token_manager import get_token_manager
    tm = get_token_manager()
    token = tm.get_access_token()
    
    if not token:
        logger.warning("TokenManager returned None, falling back to load_env()")
        credentials = load_env()
        token = credentials.get('EBAY_USER_TOKEN')
        
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Language': 'en-US'
    }


def _refresh_token_if_needed(response) -> bool:
    """Refresh token if auth failed"""
    if response.status_code in [401, 500]:
        try:
            from backend.app.core.token_manager import get_token_manager
            tm = get_token_manager()
            # Force a synchronous refresh
            return tm.force_refresh()
        except Exception as e:
            logger.error(f"Error forcing token refresh: {e}")
            pass
    return False


def ebay_request(method, url, max_retries=2, extra_headers=None, **kwargs):
    """
    Centralized eBay request wrapper.
    - Applies rate limiting
    - Handles authorization headers
    - Auto-refreshes tokens on 401
    - Retries on 429 with exponential backoff
    - Retries on transient 5xx errors

    extra_headers are merged ON TOP of the auth headers and survive the 401
    token-refresh retry (which rebuilds the auth headers from scratch).
    """
    limiter.wait_if_needed('ebay')

    if 'headers' not in kwargs:
        kwargs['headers'] = _get_headers()
    if extra_headers:
        kwargs['headers'] = {**kwargs['headers'], **extra_headers}

    last_response = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(method, url, **kwargs)
            last_response = response

            if response.status_code < 400:
                return response

            if response.status_code == 401 and attempt < max_retries:
                if _refresh_token_if_needed(response):
                    logger.info(f"Token refreshed after 401. Retrying {method} {url}...")
                    kwargs['headers'] = _get_headers()
                    if extra_headers:
                        kwargs['headers'] = {**kwargs['headers'], **extra_headers}
                    continue
                return response  # Refresh failed

            if response.status_code == 429 and attempt < max_retries:
                backoff = 2 ** attempt
                logger.warning(f"Rate limited (429), backing off {backoff}s (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(backoff)
                continue

            if response.status_code in (500, 502, 503, 504) and attempt < max_retries:
                backoff = 2 ** attempt
                logger.warning(f"Server error ({response.status_code}), retrying in {backoff}s (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(backoff)
                continue

            return response  # Non-retryable error or retries exhausted

        except requests.exceptions.RequestException as e:
            logger.warning(f"Request exception on attempt {attempt + 1}: {e}")
            if attempt >= max_retries:
                raise
            time.sleep(2 ** attempt)

    return last_response


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
    logger.info("Testing eBay Policies API...")
    
    logger.info("\nFulfillment Policies:")
    for p in get_fulfillment_policies():
        logger.info(f"  - {p['name']} ({p['id'][:20]}...): {p['description']}")
    
    logger.info("\nPayment Policies:")
    for p in get_payment_policies():
        logger.info(f"  - {p['name']} ({p['id'][:20]}...)")
    
    logger.info("\nReturn Policies:")
    for p in get_return_policies():
        logger.info(f"  - {p['name']} ({p['id'][:20]}...): {p['description']}")
    
    logger.info("\nLocations:")
    for loc in get_inventory_locations():
        logger.info(f"  - {loc['name']} ({loc['id']}): {loc['description']}")
    
    logger.info("\nCurrent Defaults:")
    defaults = get_current_defaults()
    for key, val in defaults.items():
        logger.info(f"  - {key}: {val[:20] if val else 'Not set'}...")
