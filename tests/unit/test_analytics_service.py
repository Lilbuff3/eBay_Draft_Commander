import unittest
from unittest.mock import MagicMock, patch
from backend.app.services.ebay.analytics import AnalyticsService

class TestAnalyticsService(unittest.TestCase):
    def setUp(self):
        self.service = AnalyticsService()

    def test_get_price_value_standard(self):
        pricing = {'total': {'value': '12.50', 'currency': 'USD'}}
        self.assertEqual(self.service._get_price_value(pricing), 12.50)

    def test_get_price_value_variant(self):
        pricing = {'totalAmount': {'value': '45.00'}}
        self.assertEqual(self.service._get_price_value(pricing), 45.00)

    def test_get_price_value_missing(self):
        pricing = {}
        self.assertEqual(self.service._get_price_value(pricing), 0.0)

    def test_get_price_value_malformed(self):
        pricing = {'total': {'value': 'abc'}}
        self.assertEqual(self.service._get_price_value(pricing), 0.0)

    @patch('backend.app.services.ebay.analytics.ebay_request')
    def test_get_analytics_summary_success(self, mock_request):
        # Mock actual eBay response with some weird orders
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'orders': [
                {
                    'orderId': 'order-1',
                    'creationDate': '2023-10-27T10:00:00.000Z',
                    'pricingSummary': {'total': {'value': '100.00'}},
                    'lineItems': [{'quantity': 1, 'title': 'Test Item', 'total': {'value': '100.00'}}]
                },
                {
                    'orderId': 'order-2',
                    'creationDate': '2023-10-28T10:00:00.000Z',
                    # Missing pricingSummary key should NOT crash
                    'lineItems': [{'quantity': 2, 'title': 'Another Item'}]
                }
            ],
            'total': 2
        }
        mock_request.return_value = mock_response
        
        result, status = self.service.get_analytics_summary(days=30)
        
        self.assertEqual(status, 200)
        self.assertEqual(result['total_revenue'], 100.00) # Only first order had revenue
        self.assertEqual(result['orders_count'], 2)
        self.assertEqual(result['items_sold'], 3) # 1 from order 1, 2 from order 2

    @patch('backend.app.services.ebay.analytics.ebay_request')
    def test_get_analytics_summary_empty(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'orders': [], 'total': 0}
        mock_request.return_value = mock_response
        
        result, status = self.service.get_analytics_summary(days=30)
        self.assertEqual(status, 200)
        self.assertEqual(result['total_revenue'], 0)

if __name__ == '__main__':
    unittest.main()
