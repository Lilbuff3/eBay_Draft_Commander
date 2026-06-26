import pytest
from unittest.mock import patch, MagicMock
from backend.app.services.ebay.marketing import MarketingAPI

@pytest.fixture
def mock_ebay_request():
    with patch('backend.app.services.ebay.marketing.ebay_request') as mock:
        yield mock

def test_ensure_campaign_exists(mock_ebay_request):
    api = MarketingAPI()
    
    # Mocking GET to return an existing campaign
    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.json.return_value = {
        'campaigns': [{'campaignId': '12345'}]
    }
    mock_ebay_request.return_value = mock_get_response
    
    campaign_id = api.ensure_campaign()
    assert campaign_id == '12345'
    mock_ebay_request.assert_called_once_with('GET', 'https://api.ebay.com/sell/marketing/v1/ad_campaign', params={'campaign_name': 'Draft Commander Default'})
    
    # Should use cache the second time
    mock_ebay_request.reset_mock()
    campaign_id = api.ensure_campaign()
    assert campaign_id == '12345'
    mock_ebay_request.assert_not_called()

def test_ensure_campaign_creates_new(mock_ebay_request):
    api = MarketingAPI()
    
    # Mocking GET to return empty campaigns (none found)
    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.json.return_value = {'campaigns': []}
    
    # Mocking POST to return 201 Created
    mock_post_response = MagicMock()
    mock_post_response.status_code = 201
    mock_post_response.headers = {'Location': 'https://api.ebay.com/sell/marketing/v1/ad_campaign/98765'}
    
    mock_ebay_request.side_effect = [mock_get_response, mock_post_response]
    
    campaign_id = api.ensure_campaign()
    assert campaign_id == '98765'
    assert mock_ebay_request.call_count == 2
    
    # Verify POST payload
    args, kwargs = mock_ebay_request.call_args_list[1]
    assert args[0] == 'POST'
    assert 'ad_campaign' in args[1]
    payload = kwargs['json']
    assert payload['campaignName'] == 'Draft Commander Default'
    assert payload['fundingStrategy']['bidPercentage'] == '5.0'

def test_promote_listing_success(mock_ebay_request):
    api = MarketingAPI()
    api._cached_campaign_id = '11111'  # Pretend we already got the campaign ID
    
    mock_post_response = MagicMock()
    mock_post_response.status_code = 201
    mock_ebay_request.return_value = mock_post_response
    
    result = api.promote_listing('ITEM123', 6.5)
    
    assert result['success'] is True
    assert result['listing_id'] == 'ITEM123'
    
    mock_ebay_request.assert_called_once()
    args, kwargs = mock_ebay_request.call_args
    assert args[0] == 'POST'
    assert 'ad_campaign/11111/ad' in args[1]
    assert kwargs['json']['listingId'] == 'ITEM123'
    assert kwargs['json']['bidPercentage'] == '6.5'

def test_promote_listing_failure(mock_ebay_request):
    api = MarketingAPI()
    api._cached_campaign_id = '11111'
    
    mock_post_response = MagicMock()
    mock_post_response.status_code = 400
    mock_post_response.text = 'Invalid bid percentage'
    mock_ebay_request.return_value = mock_post_response
    
    result = api.promote_listing('ITEM123', -1)
    
    assert result['success'] is False
    assert 'Status 400' in result['error']
