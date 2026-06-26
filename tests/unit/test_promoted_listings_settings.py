import pytest
from flask import Flask
from backend.app.blueprints.api.settings_api import settings_bp
from backend.app.core.settings_manager import SettingsManager

@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    class MockSettingsManager(SettingsManager):
        def __init__(self):
            super().__init__()
            self._settings = self.DEFAULTS.copy()
            self.saved_data = None
            
        def load(self):
            return self._settings
            
        def save(self, settings=None):
            if settings:
                self._settings.update(settings)
            self.saved_data = self._settings

    # Using the get_settings_manager function to patch
    manager = MockSettingsManager()
    monkeypatch.setattr('backend.app.blueprints.api.settings_api.get_settings_manager', lambda: manager)
    return manager

def test_settings_round_trip(client):
    response = client.post('/api/settings', json={
        'PROMOTED_LISTINGS_ENABLED': 'true',
        'PROMOTED_LISTINGS_AD_RATE': '7.5'
    })
    
    assert response.status_code == 200
    assert response.json['success'] is True
    
    get_response = client.get('/api/settings')
    assert get_response.json['PROMOTED_LISTINGS_ENABLED'] == 'true'
    assert get_response.json['PROMOTED_LISTINGS_AD_RATE'] == '7.5'

def test_ad_rate_clamping(client):
    # Test negative rate
    response = client.post('/api/settings', json={'PROMOTED_LISTINGS_AD_RATE': '-5.0'})
    assert response.status_code == 200
    
    get_response = client.get('/api/settings')
    assert get_response.json['PROMOTED_LISTINGS_AD_RATE'] == '0.0'
    
    # Test > 100 rate
    response = client.post('/api/settings', json={'PROMOTED_LISTINGS_AD_RATE': '150.0'})
    assert response.status_code == 200
    
    get_response = client.get('/api/settings')
    assert get_response.json['PROMOTED_LISTINGS_AD_RATE'] == '100.0'
    
    # Test invalid string rate
    response = client.post('/api/settings', json={'PROMOTED_LISTINGS_AD_RATE': 'abc'})
    assert response.status_code == 200
    
    get_response = client.get('/api/settings')
    assert get_response.json['PROMOTED_LISTINGS_AD_RATE'] == '5.0'
