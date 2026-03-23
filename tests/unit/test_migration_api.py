"""Tests for migration API endpoints"""
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


class TestMigrationCheck:

    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_check_returns_items_with_inventory_flag(self, MockTrading, client, app):
        """Items already in local DB should have inInventory=True"""
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({
            'listings': [
                {'listingId': '111', 'title': 'Item A', 'price': 19.99, 'sku': 'DC-AAA', 'imageUrl': None},
                {'listingId': '222', 'title': 'Item B', 'price': 29.99, 'sku': None, 'imageUrl': None},
            ],
            'total': 2,
            'source': 'test'
        }, 200)

        # Seed a job with listing_id '111' so it counts as "in inventory"
        with app.app_context():
            qm = app.queue_manager
            session = qm.SessionFactory()
            try:
                from backend.app.core.database import JobModel
                import uuid
                job = JobModel(id=uuid.uuid4().hex[:8], folder_path='/tmp/test', folder_name='test', status='completed', listing_id='111')
                session.add(job)
                session.commit()
            finally:
                session.close()

        resp = client.get('/api/migration/check')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'items' in data
        assert len(data['items']) == 2

        item_a = next(i for i in data['items'] if i['listingId'] == '111')
        item_b = next(i for i in data['items'] if i['listingId'] == '222')
        assert item_a['inInventory'] is True
        assert item_b['inInventory'] is False

    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_check_handles_trading_api_error(self, MockTrading, client):
        """Should return error JSON when Trading API fails"""
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({'error': 'No token'}, 500)

        resp = client.get('/api/migration/check')
        assert resp.status_code == 502
        data = resp.get_json()
        assert 'error' in data

    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_check_handles_no_listings(self, MockTrading, client):
        """Should return empty items list when no eBay listings exist"""
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({'error': 'No items found via Trading API'}, 404)

        resp = client.get('/api/migration/check')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['items'] == []


class TestMigrationExecute:

    @patch('backend.app.blueprints.api.migration_api.InventoryService')
    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_execute_creates_inventory_items(self, MockTrading, MockInventory, client):
        """Should create inventory item + offer for each listing ID"""
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({
            'listings': [
                {'listingId': '111', 'title': 'Item A', 'price': 19.99, 'sku': '', 'imageUrl': 'http://img.jpg',
                 'condition': 'Used', 'availableQuantity': 1},
            ]
        }, 200)

        mock_inv = MockInventory.return_value
        mock_inv.create_inventory_item.return_value = ({'success': True}, 200)
        mock_inv.create_offer.return_value = ({'success': True, 'offerId': 'offer123'}, 200)

        resp = client.post('/api/migration/execute', json={'listingIds': ['111']})
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['responses']) == 1
        assert data['responses'][0]['statusCode'] == 200

    def test_execute_rejects_empty_list(self, client):
        """Should 400 when no listing IDs provided"""
        resp = client.post('/api/migration/execute', json={'listingIds': []})
        assert resp.status_code == 400

    @patch('backend.app.blueprints.api.migration_api.InventoryService')
    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_execute_reports_failures(self, MockTrading, MockInventory, client):
        """Should report failure when inventory creation fails"""
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({
            'listings': [
                {'listingId': '999', 'title': 'Bad Item', 'price': 5.00, 'sku': '', 'imageUrl': None,
                 'condition': 'Used', 'availableQuantity': 1},
            ]
        }, 200)

        mock_inv = MockInventory.return_value
        mock_inv.create_inventory_item.return_value = ({'error': 'Create failed'}, 500)

        resp = client.post('/api/migration/execute', json={'listingIds': ['999']})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['responses'][0]['statusCode'] == 500

    @patch('backend.app.blueprints.api.migration_api.InventoryService')
    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_execute_listing_not_found(self, MockTrading, MockInventory, client):
        """Should 404 for listing IDs not on eBay"""
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({
            'listings': []
        }, 200)

        resp = client.post('/api/migration/execute', json={'listingIds': ['nonexistent']})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['responses'][0]['statusCode'] == 404
