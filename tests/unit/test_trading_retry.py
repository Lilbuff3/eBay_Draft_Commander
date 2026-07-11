"""Tests for token management in trading.py 401 retry and queue_manager token maintainer."""

import inspect
import pytest
from unittest.mock import patch, MagicMock


class TestTradingRetryUsesTokenManager:
    """Bug #6: Trading API 401 retry should use TokenManager, not load_env().

    The retry loop now lives in the shared _post_trading_request helper; its
    token refresh goes through _refresh_trading_token."""

    def test_401_refresh_uses_token_manager(self):
        """_refresh_trading_token should call TokenManager.force_refresh()."""
        from backend.app.services.ebay import trading

        source = inspect.getsource(trading._refresh_trading_token)
        assert 'force_refresh' in source, \
            "401 retry path should use TokenManager.force_refresh()"
        assert 'get_access_token' in source, \
            "401 retry path should use TokenManager.get_access_token() to get new token"

    def test_refresh_prefers_token_manager_over_env(self):
        """load_env() is only the last-resort fallback, after TokenManager refresh."""
        from backend.app.services.ebay import trading

        source = inspect.getsource(trading._refresh_trading_token)
        assert source.index('force_refresh') < source.index('load_env'), \
            "TokenManager refresh must be attempted before the .env fallback"

    def test_all_trading_calls_use_shared_retry_helper(self):
        """add/get/end/revise must all post through _post_trading_request."""
        from backend.app.services.ebay.trading import TradingService

        for method in (TradingService.add_fixed_price_item,
                       TradingService.get_active_listings_light,
                       TradingService.end_fixed_price_item,
                       TradingService.revise_fixed_price_item):
            source = inspect.getsource(method)
            assert '_post_trading_request' in source, \
                f"{method.__name__} should use the shared retry helper"
            assert 'requests.post' not in source, \
                f"{method.__name__} should not post directly (no retry coverage)"


class TestTokenMaintainerUsesTokenManager:
    """Bug #7: _token_maintainer should use TokenManager, not eBayOAuth(use_sandbox=False)."""

    def test_token_maintainer_does_not_hardcode_sandbox(self):
        """_token_maintainer must not contain use_sandbox=False."""
        from backend.app.services.queue_manager import QueueManager

        source = inspect.getsource(QueueManager._token_maintainer)
        assert 'use_sandbox=False' not in source, \
            "_token_maintainer should not hardcode use_sandbox=False"

    def test_token_maintainer_uses_token_manager(self):
        """_token_maintainer should use get_token_manager(), not eBayOAuth directly."""
        from backend.app.services.queue_manager import QueueManager

        source = inspect.getsource(QueueManager._token_maintainer)
        assert 'get_token_manager' in source, \
            "_token_maintainer should use get_token_manager() from token_manager module"
        assert 'eBayOAuth' not in source, \
            "_token_maintainer should not use eBayOAuth directly"
