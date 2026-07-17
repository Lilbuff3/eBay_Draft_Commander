"""Negotiation API client (offers to watchers). All HTTP mocked."""
from unittest.mock import MagicMock, patch

import pytest

from backend.app.services.ebay.negotiation import (
    NegotiationAPI, NEGOTIATION_URL,
)


def _resp(status=200, body=None, text=''):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body if body is not None else {}
    resp.text = text or str(body)
    return resp


class TestFindEligibleItems:
    def test_returns_items_with_marketplace_header(self):
        body = {'eligibleItems': [{'listingId': '111'}, {'listingId': '222'}]}
        with patch('backend.app.services.ebay.negotiation.ebay_request',
                   return_value=_resp(body=body)) as req:
            items = NegotiationAPI().find_eligible_items()
        assert [i['listingId'] for i in items] == ['111', '222']
        args, kwargs = req.call_args
        assert args[0] == 'GET'
        assert 'find_eligible_items' in args[1]
        assert kwargs['extra_headers'] == {'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US'}

    def test_follows_next_page(self):
        page1 = {'eligibleItems': [{'listingId': '1'}],
                 'next': f'{NEGOTIATION_URL}/find_eligible_items?offset=1'}
        page2 = {'eligibleItems': [{'listingId': '2'}]}
        with patch('backend.app.services.ebay.negotiation.ebay_request',
                   side_effect=[_resp(body=page1), _resp(body=page2)]) as req:
            items = NegotiationAPI().find_eligible_items()
        assert [i['listingId'] for i in items] == ['1', '2']
        assert req.call_count == 2

    def test_error_status_returns_partial(self):
        with patch('backend.app.services.ebay.negotiation.ebay_request',
                   return_value=_resp(status=403, text='forbidden')):
            items = NegotiationAPI().find_eligible_items()
        assert items == []


class TestSendOffer:
    def test_payload_shape_and_success(self):
        with patch('backend.app.services.ebay.negotiation.ebay_request',
                   return_value=_resp(status=201, body={'offers': [{}]})) as req:
            result = NegotiationAPI().send_offer('12345', 10, message='Thanks for watching!')
        assert result['success'] is True
        args, kwargs = req.call_args
        assert args[0] == 'POST'
        assert 'send_offer_to_interested_buyers' in args[1]
        payload = kwargs['json']
        assert payload['allowCounterOffer'] is False
        assert payload['message'] == 'Thanks for watching!'
        assert payload['offeredItems'] == [
            {'listingId': '12345', 'quantity': '1', 'discountPercentage': '10'}]

    def test_discount_stringified(self):
        with patch('backend.app.services.ebay.negotiation.ebay_request',
                   return_value=_resp(status=200)) as req:
            NegotiationAPI().send_offer(999, 7.5)
        payload = req.call_args.kwargs['json']
        assert payload['offeredItems'][0]['discountPercentage'] == '7.5'
        assert payload['offeredItems'][0]['listingId'] == '999'

    def test_failure_normalized(self):
        with patch('backend.app.services.ebay.negotiation.ebay_request',
                   return_value=_resp(status=403, text='insufficient_scope')):
            result = NegotiationAPI().send_offer('12345', 10)
        assert result['success'] is False
        assert '403' in result['error']

    def test_no_response_normalized(self):
        with patch('backend.app.services.ebay.negotiation.ebay_request',
                   return_value=None):
            result = NegotiationAPI().send_offer('12345', 10)
        assert result['success'] is False


class TestEbayRequestExtraHeaders:
    def test_extra_headers_merged_with_auth(self):
        from backend.app.services.ebay import policies
        captured = {}

        def fake_request(method, url, **kwargs):
            captured.update(kwargs)
            resp = MagicMock()
            resp.status_code = 200
            return resp

        with patch.object(policies, '_get_headers',
                          return_value={'Authorization': 'Bearer T'}), \
             patch.object(policies.requests, 'request', side_effect=fake_request), \
             patch.object(policies.limiter, 'wait_if_needed'):
            policies.ebay_request('GET', 'http://x',
                                  extra_headers={'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US'})
        assert captured['headers']['Authorization'] == 'Bearer T'
        assert captured['headers']['X-EBAY-C-MARKETPLACE-ID'] == 'EBAY_US'
