"""
Tests for enriched order fields in AnalyticsService.get_recent_orders().

The Orders tab / dashboard ship-by alerts depend on itemTitle, legacyItemId,
shipByDate, and paidDate being extracted from the Fulfillment API payload.
"""
from unittest.mock import MagicMock, patch

from backend.app.services.ebay.analytics import AnalyticsService


SAMPLE_ORDER = {
    "orderId": "18-14816-28552",
    "creationDate": "2026-06-28T23:15:38.000Z",
    "orderFulfillmentStatus": "NOT_STARTED",
    "buyer": {"username": "some_buyer"},
    "pricingSummary": {"total": {"value": "24.99", "currency": "USD"}},
    "paymentSummary": {"payments": [{"paymentDate": "2026-06-28T23:16:00.000Z"}]},
    "lineItems": [
        {
            "lineItemId": "111",
            "legacyItemId": "298442926679",
            "title": "Vintage Ceramic Cow Pitcher Creamer",
            "quantity": 1,
            "lineItemFulfillmentInstructions": {
                "shipByDate": "2026-06-30T06:59:59.000Z",
                "guaranteedDelivery": False,
            },
        }
    ],
}


def _mock_response(orders):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"orders": orders, "total": len(orders)}
    return resp


@patch("backend.app.services.ebay.analytics.ebay_request")
def test_orders_include_enriched_fields(mock_req):
    mock_req.return_value = _mock_response([SAMPLE_ORDER])

    result, status = AnalyticsService().get_recent_orders(days=30, limit=50)

    assert status == 200
    order = result["orders"][0]
    assert order["orderId"] == "18-14816-28552"
    assert order["itemTitle"] == "Vintage Ceramic Cow Pitcher Creamer"
    assert order["legacyItemId"] == "298442926679"
    assert order["quantity"] == 1
    assert order["shipByDate"] == "2026-06-30T06:59:59.000Z"
    assert order["paidDate"] == "2026-06-28T23:16:00.000Z"
    assert order["status"] == "NOT_STARTED"
    assert order["total"] == 24.99


@patch("backend.app.services.ebay.analytics.ebay_request")
def test_missing_optional_fields_are_none(mock_req):
    bare = {
        "orderId": "20-00000-00001",
        "orderFulfillmentStatus": "FULFILLED",
        "lineItems": [{"title": "Thing", "legacyItemId": "298000000001"}],
    }
    mock_req.return_value = _mock_response([bare])

    result, status = AnalyticsService().get_recent_orders()

    assert status == 200
    order = result["orders"][0]
    assert order["shipByDate"] is None
    assert order["paidDate"] is None
    assert order["buyer"] == "Guest"


@patch("backend.app.services.ebay.analytics.ebay_request")
def test_empty_line_items_do_not_crash(mock_req):
    mock_req.return_value = _mock_response([{"orderId": "x", "lineItems": []}])

    result, status = AnalyticsService().get_recent_orders()

    assert status == 200
    order = result["orders"][0]
    assert order["itemTitle"] is None
    assert order["itemCount"] == 0
