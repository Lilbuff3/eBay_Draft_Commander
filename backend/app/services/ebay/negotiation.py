"""eBay Sell Negotiation API — offers to interested buyers (watchers).

findEligibleItems lists active listings with interested buyers; send_offer
pushes a discounted offer to all of them at once. Requires the sell.inventory
OAuth scope (already in the app's scope set). Modeled on marketing.py: all
HTTP through ebay_request (auth + rate bucket + retries for free).
"""
from backend.app.core.logger import get_logger
from backend.app.services.ebay.policies import ebay_request

logger = get_logger('ebay_negotiation_service')

NEGOTIATION_URL = 'https://api.ebay.com/sell/negotiation/v1'
_MARKETPLACE_HEADER = {'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US'}


class NegotiationAPI:
    """Service wrapper for the eBay Sell Negotiation API."""

    def find_eligible_items(self, limit: int = 200) -> list:
        """All listings currently eligible for a seller-initiated offer.
        Follows pagination; returns [] on any error (best-effort)."""
        items = []
        url = f'{NEGOTIATION_URL}/find_eligible_items'
        params = {'limit': min(int(limit), 200)}
        try:
            while url and len(items) < limit:
                response = ebay_request('GET', url, params=params,
                                        extra_headers=_MARKETPLACE_HEADER)
                if not response or response.status_code != 200:
                    status = response.status_code if response else 'None'
                    logger.warning(f"findEligibleItems failed: {status}")
                    break
                data = response.json()
                items.extend(data.get('eligibleItems', []))
                url = data.get('next')
                params = None  # the next href already carries the query
        except Exception as e:
            logger.error(f"findEligibleItems exception: {e}")
        return items[:limit]

    def send_offer(self, listing_id, discount_pct, message: str = '') -> dict:
        """Send a discountPercentage offer to all interested buyers of one
        listing. Returns {'success', 'listing_id', 'error'?}."""
        payload = {
            'allowCounterOffer': False,
            'offeredItems': [{
                'listingId': str(listing_id),
                'quantity': '1',
                'discountPercentage': str(discount_pct),
            }],
        }
        if message:
            payload['message'] = str(message)[:2000]
        try:
            response = ebay_request(
                'POST', f'{NEGOTIATION_URL}/send_offer_to_interested_buyers',
                json=payload, extra_headers=_MARKETPLACE_HEADER)
            if response and response.status_code in (200, 201):
                return {'success': True, 'listing_id': str(listing_id)}
            status = response.status_code if response else 'None'
            error_text = response.text[:300] if response else 'No response'
            return {'success': False, 'listing_id': str(listing_id),
                    'error': f"Status {status}: {error_text}"}
        except Exception as e:
            logger.exception("send_offer failed")
            return {'success': False, 'listing_id': str(listing_id), 'error': str(e)}
