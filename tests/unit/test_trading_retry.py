"""Tests for token management in trading.py 401 retry and queue_manager token maintainer."""

import inspect
import pytest
from unittest.mock import patch, MagicMock


class TestTradingRetryUsesTokenManager:
    """Bug #6: Trading API 401 retry should use TokenManager, not load_env()."""

    def test_401_retry_calls_force_refresh(self):
        """On 401, add_fixed_price_item should call TokenManager.force_refresh(), not load_env()."""
        from backend.app.services.ebay.trading import TradingService

        source = inspect.getsource(TradingService.add_fixed_price_item)

        # The 401 handling block should use force_refresh, not load_env
        assert 'force_refresh' in source, \
            "401 retry path should use TokenManager.force_refresh()"
        assert 'get_access_token' in source, \
            "401 retry path should use TokenManager.get_access_token() to get new token"

    def test_401_retry_does_not_use_load_env_for_refresh(self):
        """The 401 retry code path should not call load_env() to get a refreshed token."""
        from backend.app.services.ebay.trading import TradingService

        source = inspect.getsource(TradingService.add_fixed_price_item)

        # Find text between '401' and the next elif/else to isolate the 401 block
        idx_401 = source.find('401')
        idx_next = source.find('elif', idx_401 + 1)
        if idx_next == -1:
            idx_next = len(source)
        block_401 = source[idx_401:idx_next]

        assert 'load_env' not in block_401, \
            "401 retry block should not use load_env() — use TokenManager instead"


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
