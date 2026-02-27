
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask, jsonify

# Add backend to path
sys.path.append(os.getcwd())

from backend.app.blueprints.api.listings_api import listings_bp
from backend.app.services.queue_job import JobStatus

class TestListingsAPI(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(listings_bp, url_prefix='/api')
        self.client = self.app.test_client()
        
        # Mock QueueManager
        self.mock_qm = MagicMock()
        self.app.config['QUEUE_MANAGER'] = self.mock_qm

    def test_get_pending_listings(self):
        mock_session = MagicMock()
        self.mock_qm.SessionFactory.return_value = mock_session
        self.mock_qm.JobModel = MagicMock()
        self.mock_qm._db_to_queue_job.return_value.to_dict.return_value = {'id': 'J1', 'status': 'pending_review'}
        mock_session.query.return_value.filter_by.return_value.all.return_value = [MagicMock()]
        
        response = self.client.get('/api/listings/pending')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data['listings']), 1)
        self.assertEqual(data['listings'][0]['id'], 'J1')

    def test_quick_edit(self):
        self.mock_qm.update_job.return_value = True
        
        response = self.client.put('/api/listings/J1/quick-edit', json={
            'title': 'New Title',
            'price': '20.00',
            'condition': 'LIKE_NEW'
        })
        
        self.assertEqual(response.status_code, 200)
        self.mock_qm.update_job.assert_called_once_with('J1', {
            'user_title': 'New Title',
            'user_price': '20.00',
            'user_condition': 'LIKE_NEW'
        })

    def test_batch_approve(self):
        self.mock_qm.update_job.return_value = True
        self.mock_qm.is_processing.return_value = False
        self.mock_qm.is_paused.return_value = False
        
        response = self.client.post('/api/listings/batch-approve', json={
            'listing_ids': ['J1', 'J2']
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mock_qm.update_job.call_count, 2)
        self.mock_qm.start_processing.assert_called_once()

if __name__ == "__main__":
    unittest.main()
