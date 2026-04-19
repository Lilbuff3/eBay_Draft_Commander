"""
Tests for Fix 3: GEMINI_RPM_LIMIT should be env-configurable.

Verifies that the constant reads from environment variable
and falls back to the default of 2 when not set.
"""

import os
import importlib
import pytest


class TestGeminiRpmConfig:
    """GEMINI_RPM_LIMIT should read from env var with default of 60 (paid tier)."""

    def test_default_value_is_60(self, monkeypatch):
        """When GEMINI_RPM_LIMIT is not in env, default to 60."""
        monkeypatch.delenv('GEMINI_RPM_LIMIT', raising=False)
        import backend.app.core.constants as constants_mod
        importlib.reload(constants_mod)

        assert constants_mod.GEMINI_RPM_LIMIT == 60

    def test_env_override_to_60(self, monkeypatch):
        """When GEMINI_RPM_LIMIT=60 in env, constant should be 60."""
        monkeypatch.setenv('GEMINI_RPM_LIMIT', '60')
        import backend.app.core.constants as constants_mod
        importlib.reload(constants_mod)

        assert constants_mod.GEMINI_RPM_LIMIT == 60

    def test_req_interval_recalculated(self, monkeypatch):
        """GEMINI_REQ_INTERVAL should recalculate from the new RPM limit."""
        monkeypatch.setenv('GEMINI_RPM_LIMIT', '60')
        import backend.app.core.constants as constants_mod
        importlib.reload(constants_mod)

        assert constants_mod.GEMINI_REQ_INTERVAL == 1.0  # 60/60 = 1s

    def test_settings_manager_has_gemini_rpm(self):
        """GEMINI_RPM_LIMIT should appear in AI Settings category."""
        from backend.app.core.settings_manager import SettingsManager

        ai_keys = SettingsManager.SETTING_CATEGORIES.get('AI Settings', [])
        assert 'GEMINI_RPM_LIMIT' in ai_keys, \
            "GEMINI_RPM_LIMIT should be in the AI Settings category"
