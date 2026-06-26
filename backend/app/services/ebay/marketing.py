import datetime
from backend.app.core.logger import get_logger
from backend.app.services.ebay.policies import ebay_request

logger = get_logger('ebay_marketing_service')

MARKETING_URL = 'https://api.ebay.com/sell/marketing/v1'

class MarketingAPI:
    """Service for handling eBay Sell Marketing API (Promoted Listings)"""

    def __init__(self):
        self._cached_campaign_id = None

    def ensure_campaign(self) -> str:
        """
        Find or create a default Promoted Listings Standard campaign.
        Returns the campaign_id.
        """
        if self._cached_campaign_id:
            return self._cached_campaign_id

        campaign_name = "Draft Commander Default"

        # 1. Try to find the campaign
        try:
            response = ebay_request('GET', f'{MARKETING_URL}/ad_campaign', params={'campaign_name': campaign_name})
            if response and response.status_code == 200:
                data = response.json()
                campaigns = data.get('campaigns', [])
                if campaigns:
                    self._cached_campaign_id = campaigns[0].get('campaignId')
                    return self._cached_campaign_id
        except Exception as e:
            logger.warning(f"Error fetching existing campaigns: {e}")
            # Continue to try creating if we failed to fetch for some reason, 
            # though it might fail if one exists.

        # 2. Create the campaign if not found
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            payload = {
                "campaignName": campaign_name,
                "fundingStrategy": {
                    "fundingModel": "COST_PER_SALE",
                    "bidPercentage": "5.0" # Default, can be overridden per-ad
                },
                "marketplaceId": "EBAY_US",
                "startDate": now.strftime('%Y-%m-%dT%H:%M:%SZ')
            }
            response = ebay_request('POST', f'{MARKETING_URL}/ad_campaign', json=payload)
            if response and response.status_code == 201:
                # Campaign ID is usually in the Location header
                location = response.headers.get('Location', '')
                if location:
                    campaign_id = location.rstrip('/').split('/')[-1]
                    self._cached_campaign_id = campaign_id
                    return campaign_id
            
            # If 201 but no location, or some other success code?
            logger.error(f"Failed to create campaign. Status: {response.status_code if response else 'None'}")
        except Exception as e:
            logger.error(f"Exception creating campaign: {e}")

        return ""

    def promote_listing(self, listing_id: str, ad_rate_percent: float) -> dict:
        """
        Add the listing as an ad under the default campaign at the given bid percentage.
        """
        try:
            campaign_id = self.ensure_campaign()
            if not campaign_id:
                return {'success': False, 'error': 'Could not get or create campaign'}

            payload = {
                "listingId": listing_id,
                "bidPercentage": str(float(ad_rate_percent))
            }
            
            response = ebay_request('POST', f'{MARKETING_URL}/ad_campaign/{campaign_id}/ad', json=payload)
            if response and response.status_code in [201, 200]:
                return {'success': True, 'listing_id': listing_id}
            
            error_msg = response.text if response else 'Unknown error'
            return {'success': False, 'error': f"Status {response.status_code if response else 'None'}: {error_msg}"}
        except Exception as e:
            logger.exception("Error in promote_listing")
            return {'success': False, 'error': str(e)}
