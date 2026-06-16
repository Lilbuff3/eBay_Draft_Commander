"""
Unit tests for the no-blocks required-aspect resolver.

`AIAnalyzer.resolve_missing_required_aspects()` MUST return a value for every
missing required aspect so the pipeline never blocks on missing data:
  - a valid model value (in the allowed list when constrained, above the
    confidence floor) is used, OR
  - a deterministic safe default is filled (first allowed value, else
    "Does Not Apply").

Gemini is always mocked — no live calls.
"""
import json
from unittest.mock import MagicMock

import pytest

from backend.app.services.ai_analyzer import AIAnalyzer


def _analyzer_with_response(payload):
    """An AIAnalyzer whose Gemini client returns `payload` (dict) as JSON text."""
    analyzer = AIAnalyzer.__new__(AIAnalyzer)  # skip __init__ (no API key needed)
    analyzer.client = MagicMock()
    analyzer.client.models.generate_content.return_value = MagicMock(
        text=json.dumps(payload)
    )
    return analyzer


def _resolve(analyzer, missing):
    return analyzer.resolve_missing_required_aspects(
        missing=missing,
        title="Test item",
        identification={},
        category_name="Test Category",
        image_paths=[],
        research_specs=None,
    )


CONSTRAINED = [{"name": "Color", "values": ["Black", "White", "Red"]}]
FREE_TEXT = [{"name": "Pattern", "values": []}]


def test_valid_in_list_value_is_used():
    analyzer = _analyzer_with_response(
        {"Color": {"value": "Black", "confidence": 0.9, "source": "image"}}
    )
    out = _resolve(analyzer, CONSTRAINED)
    assert out["Color"]["value"] == "Black"


def test_out_of_list_value_falls_back_to_allowed():
    analyzer = _analyzer_with_response(
        {"Color": {"value": "Magenta", "confidence": 0.95, "source": "image"}}
    )
    out = _resolve(analyzer, CONSTRAINED)
    # Magenta is not allowed -> deterministic fallback to a valid allowed value
    assert out["Color"]["value"] in ["Black", "White", "Red"]
    assert out["Color"]["source"] == "default"


def test_low_confidence_falls_back():
    analyzer = _analyzer_with_response(
        {"Color": {"value": "Red", "confidence": 0.1, "source": "inferred"}}
    )
    out = _resolve(analyzer, CONSTRAINED)
    assert out["Color"]["source"] == "default"


def test_every_missing_aspect_gets_a_value():
    analyzer = _analyzer_with_response({})  # model returns nothing
    missing = CONSTRAINED + FREE_TEXT
    out = _resolve(analyzer, missing)
    assert set(out.keys()) == {"Color", "Pattern"}
    assert out["Color"]["value"]  # non-empty
    assert out["Pattern"]["value"] == "Does Not Apply"  # free-text default


def test_gemini_exception_does_not_raise_and_fills_defaults():
    analyzer = AIAnalyzer.__new__(AIAnalyzer)
    analyzer.client = MagicMock()
    analyzer.client.models.generate_content.side_effect = RuntimeError("boom")
    out = _resolve(analyzer, CONSTRAINED)
    assert out["Color"]["value"] in ["Black", "White", "Red"]
    assert out["Color"]["source"] == "default"


def test_no_client_fills_defaults():
    analyzer = AIAnalyzer.__new__(AIAnalyzer)
    analyzer.client = None
    out = _resolve(analyzer, CONSTRAINED)
    assert out["Color"]["value"] in ["Black", "White", "Red"]


def test_empty_missing_returns_empty():
    analyzer = _analyzer_with_response({})
    assert _resolve(analyzer, []) == {}
