
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add backend to path
sys.path.append(os.getcwd())

from backend.app.services.processor_service import ProcessorService
from backend.app.services.queue_job import QueueJob, JobStatus

class TestProcessorIntercept(unittest.TestCase):
    def setUp(self):
        self.processor = ProcessorService()
        self.job = QueueJob(id="TEST", folder_path="test", folder_name="test")
        
        # Mock dependencies to avoid actual API/AI calls
        self.processor.ai_agent.analyze_item = MagicMock()
        self.processor.category_mapper.get_category = MagicMock(return_value={'id': '1', 'name': 'Test'})
        self.processor.ai_agent.get_final_pricing = MagicMock(return_value={'price': '10.00', 'timing': 0})
        self.processor.image_processor.upload_images = MagicMock(return_value={'urls': [], 'timing': 0})
        self.processor._render_listing_template = MagicMock(return_value={'html': 'test', 'timing': 0})
        self.processor._create_trading_api_listing = MagicMock(return_value={'success': True, 'listing_id': '123', 'status': 'Active', 'timing': 0})
        
        # Common mocks for all tests
        Path.exists = MagicMock(return_value=True)
        Path.iterdir = MagicMock(return_value=[Path("test/img.jpg")])

    @patch.dict(os.environ, {"AUTO_PUBLISH": "true", "CONFIDENCE_THRESHOLD": "0.85"})
    def test_auto_publish_high_confidence(self):
        self.processor.ai_agent.analyze_item.return_value = {
            'success': True, 'title': 'Test', 'raw_description': 'Test', 
            'item_specifics': {}, 'ai_suggested_price': '10.00', 
            'shipping_cost': 0, 'confidence_score': 0.95
        }
        
        result = self.processor.create_listing(self.job)
        self.assertEqual(result['status'], 'Active')
        print(f"✅ Success: Auto-publish high confidence -> {result['status']}")

    @patch.dict(os.environ, {"AUTO_PUBLISH": "true", "CONFIDENCE_THRESHOLD": "0.85"})
    def test_auto_publish_low_confidence(self):
        self.processor.ai_agent.analyze_item.return_value = {
            'success': True, 'title': 'Test', 'raw_description': 'Test', 
            'item_specifics': {}, 'ai_suggested_price': '10.00', 
            'shipping_cost': 0, 'confidence_score': 0.80
        }
        
        result = self.processor.create_listing(self.job)
        self.assertEqual(result['status'], 'pending_review')

    @patch.dict(os.environ, {"AUTO_PUBLISH": "false"})
    def test_manual_publish_high_confidence(self):
        self.processor.ai_agent.analyze_item.return_value = {
            'success': True, 'title': 'Test', 'raw_description': 'Test', 
            'item_specifics': {}, 'ai_suggested_price': '10.00', 
            'shipping_cost': 0, 'confidence_score': 0.99
        }
        
        result = self.processor.create_listing(self.job)
        self.assertEqual(result['status'], 'pending_review')

if __name__ == "__main__":
    # Create the app context for current_app.config access
    from flask import Flask
    app = Flask(__name__)
    app.config['EBAY_PAYMENT_POLICY'] = 'P1'
    app.config['EBAY_RETURN_POLICY'] = 'R1'
    app.config['EBAY_FULFILLMENT_POLICY'] = 'F1'
    app.config['EBAY_POSTAL_CODE'] = '12345'
    
    with app.app_context():
        unittest.main(argv=['first-arg-is-ignored'], exit=False)
