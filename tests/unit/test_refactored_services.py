
import unittest
from unittest.mock import MagicMock, patch, Mock
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.services.ai_analyzer import AIAnalyzer
from backend.app.services.ebay.researcher import eBayResearcher, SoldItem
from backend.app.services.ebay.browse import eBayBrowseAPI, MarketItem
from backend.app.core.constants import AI_MODEL_NAME

class TestAIAnalyzer(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.analyzer = AIAnalyzer()
        self.analyzer.client = self.mock_client

    @patch('PIL.Image.open', return_value=MagicMock())
    @patch('backend.app.services.ai_analyzer.limiter')
    def test_analyze_item_success(self, mock_limiter, mock_pil):
        # Mock successful Gemini response with ALL required keys
        mock_response = MagicMock()
        mock_response.text = '{"identification": {"brand": "TestBrand"}, "listing": {"suggested_price": 100}}'
        self.mock_client.models.generate_content.return_value = mock_response

        # Mock image encoding
        with patch.object(self.analyzer, 'encode_image', return_value='base64_string'):
            result = self.analyzer.analyze_item(['path/to/image.jpg'])

        self.assertNotIn('error', result)
        self.assertEqual(result['identification']['brand'], 'TestBrand')
        self.mock_client.models.generate_content.assert_called_once()
        args, kwargs = self.mock_client.models.generate_content.call_args
        self.assertEqual(kwargs['model'], AI_MODEL_NAME)

    @patch('PIL.Image.open', return_value=MagicMock())
    @patch('backend.app.services.ai_analyzer.limiter')
    def test_analyze_item_json_parsing_robustness(self, mock_limiter, mock_pil):
        # Test with markdown code blocks AND complete JSON
        mock_response = MagicMock()
        mock_text = """```json
{"identification": {"brand": "MarkdownBrand"}, "listing": {"title": "Test"}}
```"""
        mock_response.text = mock_text
        self.mock_client.models.generate_content.return_value = mock_response

        with patch.object(self.analyzer, 'encode_image', return_value='base64_string'):
            result = self.analyzer.analyze_item(['path/to/image.jpg'])

        self.assertNotIn('error', result)
        self.assertEqual(result['identification']['brand'], 'MarkdownBrand')

    @patch('backend.app.services.ai_analyzer.limiter')
    def test_research_part_number_success(self, mock_limiter):
        # Mock successful research response
        mock_response = MagicMock()
        mock_response.text = '{"market_price": {"low": 10, "high": 20}}'
        # Mock grounding metadata
        mock_candidate = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.web.title = "Test Source"
        mock_chunk.web.uri = "http://test.com"
        mock_candidate.grounding_metadata.grounding_chunks = [mock_chunk]
        mock_response.candidates = [mock_candidate]
        
        self.mock_client.models.generate_content.return_value = mock_response

        result = self.analyzer.research_part_number("Brand", "Model")
        
        self.assertTrue(result['researched'])
        self.assertEqual(len(result['sources']), 1)
        self.assertEqual(result['sources'][0]['title'], "Test Source")
        self.assertIn('market_price', result)


class TesteBayServices(unittest.TestCase):
    def test_browse_api_item_to_dict(self):
        # Verify Browse API item mapping includes imageUrl and soldDate
        api = eBayBrowseAPI()
        item = MarketItem(
            title="Test Item",
            price=50.0,
            condition="Used",
            image_url="http://image.url",
            item_url="http://item.url",
            seller="seller1"
        )
        data = api._item_to_dict(item)
        
        self.assertEqual(data['title'], "Test Item")
        self.assertEqual(data['price'], 50.0)
        self.assertEqual(data['imageUrl'], "http://image.url")
        self.assertEqual(data['soldDate'], "Active")
        self.assertEqual(data['date'], "Active")

    def test_researcher_scraping_parsing(self):
        # Verify Researcher parsing logic via _item_to_dict compatibility
        researcher = eBayResearcher()
        
        # Use SoldItem for researcher._item_to_dict
        sold_item = SoldItem(
            title="Scraped Item",
            price=45.0,
            shipping=5.0,
            date="Nov 12",
            condition="Used",
            url="http://item.url",
            image_url="http://scraped.image"
        )
        
        data = researcher._item_to_dict(sold_item)
        self.assertEqual(data['imageUrl'], "http://scraped.image")
        self.assertEqual(data['soldDate'], "Nov 12")
        self.assertEqual(data['shipping'], 5.0)

if __name__ == '__main__':
    unittest.main()
