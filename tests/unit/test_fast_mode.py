"""Tests for FAST_MODE: skip Phase 2 web research + Gemini price grounding."""
from unittest.mock import MagicMock


class TestFastModeSettingsRegistration:
    def test_fast_mode_in_automation_category(self):
        from backend.app.core.settings_manager import SettingsManager
        auto_keys = SettingsManager.SETTING_CATEGORIES.get('Automation', [])
        assert 'FAST_MODE' in auto_keys

    def test_fast_mode_default_false(self):
        from backend.app.core.settings_manager import SettingsManager
        assert SettingsManager.DEFAULTS.get('FAST_MODE') == 'false'


class TestFastModeSkipsGeminiGrounding:
    def _make_engine(self):
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine.__new__(PricingEngine)
        engine.app_id = "test"
        engine.google_api_key = None
        engine.ai_client = None
        engine.search_sold_listings = MagicMock(return_value=[])
        engine.generate_ebay_search_link = MagicMock(return_value="")
        engine.get_ai_price_estimate = MagicMock(
            return_value={"price": 99.99, "reasoning": "grounded"}
        )
        return engine

    def test_fast_mode_skips_gemini_grounding(self, monkeypatch):
        monkeypatch.setenv('FAST_MODE', 'true')
        engine = self._make_engine()

        result = engine.get_price_with_comps(
            "Widget",
            condition="Used - Good",
            research_market_price=None,
            shipping_cost=0,
            ai_suggested_price="30.00",
        )

        engine.get_ai_price_estimate.assert_not_called()
        assert result["source"] == "ai_estimate"

    def test_fast_mode_false_runs_gemini_grounding(self, monkeypatch):
        monkeypatch.setenv('FAST_MODE', 'false')
        engine = self._make_engine()

        result = engine.get_price_with_comps(
            "Widget",
            condition="Used - Good",
            research_market_price=None,
            shipping_cost=0,
            ai_suggested_price="30.00",
        )

        engine.get_ai_price_estimate.assert_called_once()
        assert result["source"] == "ai_grounded_research"

    def test_fast_mode_unset_defaults_to_off(self, monkeypatch):
        monkeypatch.delenv('FAST_MODE', raising=False)
        engine = self._make_engine()

        engine.get_price_with_comps(
            "Widget",
            condition="Used - Good",
            research_market_price=None,
            shipping_cost=0,
            ai_suggested_price="30.00",
        )

        engine.get_ai_price_estimate.assert_called_once()


class TestFastModeSkipsPhase2Research:
    def _make_analyzer(self):
        from backend.app.services.ai_analyzer import AIAnalyzer
        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        analyzer.client = MagicMock()
        analyzer.analyze_item = MagicMock(return_value={
            "identification": {
                "brand": "Sony",
                "model": "WH-1000XM5",
                "mpn": "WH1000XM5",
                "product_type": "Headphones",
                "material": "plastic",
            },
            "listing": {"suggested_title": "Sony Headphones", "suggested_price": "200"},
            "condition": {"state": "Used"},
        })
        analyzer.research_part_number = MagicMock(return_value={"researched": False})
        return analyzer

    def test_fast_mode_skips_research_call(self, monkeypatch):
        monkeypatch.setenv('FAST_MODE', 'true')
        analyzer = self._make_analyzer()

        result = analyzer.analyze_with_research(["fake.jpg"], "")

        analyzer.research_part_number.assert_not_called()
        assert result.get('analysis_mode') == 'basic'

    def test_fast_mode_off_runs_research_call(self, monkeypatch):
        monkeypatch.setenv('FAST_MODE', 'false')
        analyzer = self._make_analyzer()

        analyzer.analyze_with_research(["fake.jpg"], "")

        analyzer.research_part_number.assert_called_once()
