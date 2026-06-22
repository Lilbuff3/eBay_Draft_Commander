"""Regression: pricing must not crash on None-valued identifier fields.

A None value (e.g. {"brand": None}) made `_build_keyword_query` call None.strip(),
which aborted the whole pricing cascade before Gemini grounding ever ran, so the
price defaulted instead of being reasoned. Guard with `or ''`.
"""
from backend.app.services.pricing_engine import PricingEngine


def test_build_keyword_query_handles_none_identifiers():
    eng = PricingEngine.__new__(PricingEngine)
    # None values (not just missing keys) must not raise.
    q = eng._build_keyword_query("Acme Widget 12345", {
        "brand": None, "mpn": None, "model": None, "product_type": None,
    })
    assert isinstance(q, str) and q  # falls back to title-derived query


def test_build_keyword_query_uses_identifiers():
    eng = PricingEngine.__new__(PricingEngine)
    q = eng._build_keyword_query("ignored title text", {
        "brand": "Sony", "mpn": "WH-1000XM5", "product_type": "Headphones",
    })
    assert "Sony" in q
