"""
Tests for configuration consistency across backend modules.

Validates that env var names, defaults, and config loading patterns
are consistent between config.py, constants.py, and settings_manager.py.
"""
import inspect
import os
import unittest
from unittest.mock import patch


class TestAutoPublishEnvVar(unittest.TestCase):
    """Bug #11: AUTO_PUBLISH env var name must match between config.py and settings_manager.py."""

    def test_config_uses_auto_publish_not_ebay_auto_publish(self):
        """Config.py should read AUTO_PUBLISH, not EBAY_AUTO_PUBLISH."""
        import backend.config
        source = inspect.getsource(backend.config.Config)
        self.assertNotIn('EBAY_AUTO_PUBLISH', source,
                         "Config still references EBAY_AUTO_PUBLISH instead of AUTO_PUBLISH")
        self.assertIn("AUTO_PUBLISH", source,
                      "Config should reference AUTO_PUBLISH")


class TestDefaultConditionFromEnv(unittest.TestCase):
    """Bug #15: DEFAULT_CONDITION should respect env var override."""

    def test_default_condition_respects_env(self):
        """DEFAULT_CONDITION should pick up value from os.environ."""
        with patch.dict(os.environ, {'DEFAULT_CONDITION': 'NEW'}):
            # Re-import to pick up patched env
            import importlib
            import backend.app.core.constants as constants_mod
            importlib.reload(constants_mod)
            self.assertEqual(constants_mod.DEFAULT_CONDITION, 'NEW')

    def test_default_condition_fallback(self):
        """DEFAULT_CONDITION should fall back to USED_EXCELLENT when env is unset."""
        env = os.environ.copy()
        env.pop('DEFAULT_CONDITION', None)
        with patch.dict(os.environ, env, clear=True):
            import importlib
            import backend.app.core.constants as constants_mod
            importlib.reload(constants_mod)
            self.assertEqual(constants_mod.DEFAULT_CONDITION, 'USED_EXCELLENT')


class TestISBNScannerConfig(unittest.TestCase):
    """Bug #25: ISBNScanner should not manually parse .env files."""

    def test_init_does_not_use_parents_path(self):
        """ISBNScanner.__init__ should not reference parents[3] for .env parsing."""
        from backend.app.services.isbn_scanner import ISBNScanner
        source = inspect.getsource(ISBNScanner.__init__)
        self.assertNotIn('parents[3]', source,
                         "ISBNScanner.__init__ still uses parents[3] path hack")
        self.assertNotIn('env_path', source,
                         "ISBNScanner.__init__ should not manually parse .env files")


if __name__ == '__main__':
    unittest.main()
