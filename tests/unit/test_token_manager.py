"""Tests for TokenManager — eBay access token lifecycle.

Covers token validity checks, storage, OAuth refresh, and status reporting.
All DB access is mocked to keep tests self-contained.
"""
import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from backend.app.core.token_manager import TokenManager, REFRESH_BUFFER_SECONDS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tm():
    """Build a TokenManager with DB methods mocked out."""
    with patch.object(TokenManager, '_load_from_db'):
        with patch.object(TokenManager, '_save_to_db'):
            manager = TokenManager()
    return manager


@pytest.fixture
def mock_settings():
    """Mock get_settings_manager so no .env I/O happens."""
    mock = MagicMock()
    mock.get.return_value = None  # default: no credentials configured
    with patch('backend.app.core.token_manager.get_settings_manager', return_value=mock):
        yield mock


def _setup_credentials(mock_settings):
    """Configure mock_settings to return valid eBay credentials."""
    mapping = {
        'EBAY_REFRESH_TOKEN': 'fake-refresh',
        'EBAY_APP_ID': 'fake-app-id',
        'EBAY_CERT_ID': 'fake-cert-id',
        'EBAY_ENVIRONMENT': 'production',
    }

    def get_side_effect(key, default=None):
        return mapping.get(key, default)

    mock_settings.get.side_effect = get_side_effect


# ---------------------------------------------------------------------------
# TestTokenValidity — _is_valid() and get_access_token() behaviour
# ---------------------------------------------------------------------------

class TestTokenValidity:
    def test_valid_token_returned_directly(self, tm):
        """A cached, non-expired token is returned without calling _refresh."""
        tm._access_token = "tok123"
        tm._expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        with patch.object(tm, '_refresh') as mock_refresh:
            result = tm.get_access_token()

        assert result == "tok123"
        mock_refresh.assert_not_called()

    def test_expired_triggers_refresh(self, tm, mock_settings):
        """An expired token triggers a refresh attempt."""
        tm._access_token = "old-tok"
        tm._expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)

        with patch.object(tm, '_refresh', return_value=True) as mock_refresh:
            tm._access_token = "refreshed-tok"  # simulate what _refresh would do
            tm.get_access_token()

        mock_refresh.assert_called_once()

    def test_buffer_9min_is_invalid(self, tm):
        """A token expiring in 9 minutes is inside the 10-min buffer, so invalid."""
        tm._access_token = "tok"
        tm._expires_at = datetime.now(timezone.utc) + timedelta(minutes=9)

        assert tm._is_valid() is False

    def test_buffer_11min_is_valid(self, tm):
        """A token expiring in 11 minutes is outside the 10-min buffer, so valid."""
        tm._access_token = "tok"
        tm._expires_at = datetime.now(timezone.utc) + timedelta(minutes=11)

        assert tm._is_valid() is True

    def test_no_token_no_refresh_returns_none(self, tm, mock_settings):
        """No cached token + failed refresh returns None."""
        tm._access_token = None
        tm._expires_at = None

        with patch.object(tm, '_refresh', return_value=False):
            result = tm.get_access_token()

        assert result is None

    def test_refresh_fails_returns_expired_token(self, tm, mock_settings):
        """If refresh fails but we have an expired token, return it anyway."""
        tm._access_token = "stale-tok"
        tm._expires_at = datetime.now(timezone.utc) - timedelta(minutes=30)

        with patch.object(tm, '_refresh', return_value=False):
            result = tm.get_access_token()

        assert result == "stale-tok"


# ---------------------------------------------------------------------------
# TestTokenStorage — store_tokens() behaviour
# ---------------------------------------------------------------------------

class TestTokenStorage:
    def test_store_sets_memory_and_env(self, tm, mock_settings):
        """store_tokens persists token in memory and os.environ."""
        with patch.object(tm, '_save_to_db'):
            tm.store_tokens("new-tok")

        assert tm._access_token == "new-tok"
        assert os.environ.get('EBAY_USER_TOKEN') == "new-tok"
        assert tm._expires_at is not None

    def test_store_saves_refresh_to_settings(self, tm, mock_settings):
        """When a refresh_token is supplied, it is written via SettingsManager."""
        with patch.object(tm, '_save_to_db'):
            tm.store_tokens("tok", refresh_token="ref-tok")

        mock_settings.set.assert_any_call('EBAY_REFRESH_TOKEN', 'ref-tok')
        mock_settings.save.assert_called_once()
        assert os.environ.get('EBAY_REFRESH_TOKEN') == "ref-tok"

    def test_store_no_refresh_skips_settings(self, tm, mock_settings):
        """Without a refresh_token, SettingsManager is not invoked."""
        with patch.object(tm, '_save_to_db'):
            tm.store_tokens("tok", refresh_token=None)

        mock_settings.set.assert_not_called()
        mock_settings.save.assert_not_called()


# ---------------------------------------------------------------------------
# TestTokenRefresh — _refresh() behaviour
# ---------------------------------------------------------------------------

class TestTokenRefresh:
    def test_successful_refresh(self, tm, mock_settings):
        """A 200 response updates the in-memory token and returns True."""
        _setup_credentials(mock_settings)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'access_token': 'fresh-tok',
            'expires_in': 7200,
        }

        with patch('backend.app.core.token_manager.requests.post', return_value=mock_resp):
            with patch.object(tm, '_save_to_db'):
                result = tm._refresh()

        assert result is True
        assert tm._access_token == 'fresh-tok'
        assert tm._expires_at is not None
        assert os.environ.get('EBAY_USER_TOKEN') == 'fresh-tok'

    def test_refresh_failure_401(self, tm, mock_settings):
        """A non-200 response returns False without modifying the token."""
        _setup_credentials(mock_settings)

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        with patch('backend.app.core.token_manager.requests.post', return_value=mock_resp):
            result = tm._refresh()

        assert result is False

    def test_missing_refresh_token(self, tm, mock_settings):
        """Without EBAY_REFRESH_TOKEN, no HTTP call is made and returns False."""
        # mock_settings.get returns None by default (no credentials)
        with patch('backend.app.core.token_manager.requests.post') as mock_post:
            result = tm._refresh()

        assert result is False
        mock_post.assert_not_called()

    def test_missing_credentials(self, tm, mock_settings):
        """Without APP_ID/CERT_ID, no HTTP call is made and returns False."""
        def get_side_effect(key, default=None):
            if key == 'EBAY_REFRESH_TOKEN':
                return 'fake-refresh'
            return default  # APP_ID, CERT_ID -> None

        mock_settings.get.side_effect = get_side_effect

        with patch('backend.app.core.token_manager.requests.post') as mock_post:
            result = tm._refresh()

        assert result is False
        mock_post.assert_not_called()

    def test_network_error(self, tm, mock_settings):
        """A network error is caught and returns False."""
        _setup_credentials(mock_settings)

        with patch('backend.app.core.token_manager.requests.post', side_effect=ConnectionError("timeout")):
            result = tm._refresh()

        assert result is False

    def test_token_rotation(self, tm, mock_settings):
        """When eBay rotates the refresh token, the new one is saved."""
        _setup_credentials(mock_settings)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'access_token': 'fresh-tok',
            'expires_in': 7200,
            'refresh_token': 'rotated-refresh',
        }

        with patch('backend.app.core.token_manager.requests.post', return_value=mock_resp):
            with patch.object(tm, '_save_to_db'):
                result = tm._refresh()

        assert result is True
        mock_settings.set.assert_any_call('EBAY_REFRESH_TOKEN', 'rotated-refresh')
        mock_settings.save.assert_called_once()
        assert os.environ.get('EBAY_REFRESH_TOKEN') == 'rotated-refresh'


# ---------------------------------------------------------------------------
# TestGetTokenStatus — get_token_status() diagnostics
# ---------------------------------------------------------------------------

class TestGetTokenStatus:
    def test_valid_token_status(self, tm, mock_settings):
        """A valid token reports has_access_token=True, is_expired=False."""
        tm._access_token = "tok"
        tm._expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        status = tm.get_token_status()

        assert status['has_access_token'] is True
        assert status['is_expired'] is False
        assert status['expires_at'] is not None

    def test_expired_token_status(self, tm, mock_settings):
        """An expired token reports is_expired=True."""
        tm._access_token = "tok"
        tm._expires_at = datetime.now(timezone.utc) - timedelta(minutes=30)

        status = tm.get_token_status()

        assert status['has_access_token'] is True
        assert status['is_expired'] is True

    def test_no_token_status(self, tm, mock_settings):
        """No token at all reports has_access_token=False, is_expired=None."""
        tm._access_token = None
        tm._expires_at = None

        status = tm.get_token_status()

        assert status['has_access_token'] is False
        assert status['is_expired'] is None
        assert status['expires_at'] is None
