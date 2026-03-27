"""Tests for GET /api/lookup/category/<id>/conditions"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def app(tmp_path):
    from backend.app import create_app
    from backend.app.services.queue_manager import QueueManager
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestValidConditionsEndpoint:
    @patch('backend.app.blueprints.api.lookup_api.get_valid_condition_ids')
    def test_returns_valid_conditions(self, mock_get_ids, client):
        mock_get_ids.return_value = ['1000', '1500', '3000', '5000']
        resp = client.get('/api/lookup/category/175673/conditions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['category_id'] == '175673'
        assert len(data['conditions']) == 4
        assert all('id' in c and 'label' in c for c in data['conditions'])

    @patch('backend.app.blueprints.api.lookup_api.get_valid_condition_ids')
    def test_unknown_category_returns_empty(self, mock_get_ids, client):
        mock_get_ids.return_value = []
        resp = client.get('/api/lookup/category/999999/conditions')
        assert resp.status_code == 200
        assert resp.get_json()['condition_ids'] == []

    @patch('backend.app.blueprints.api.lookup_api.get_valid_condition_ids')
    def test_condition_labels_are_human_readable(self, mock_get_ids, client):
        mock_get_ids.return_value = ['1000', '7000']
        resp = client.get('/api/lookup/category/123/conditions')
        data = resp.get_json()
        labels = [c['label'] for c in data['conditions']]
        assert 'New' in labels
        assert 'For Parts Or Not Working' in labels
