import pytest
from backend.app.services.listing_guardrails import (
    clean_title,
    optimize_cassini_title,
)

class TestCassiniTitleOptimizer:
    def test_strips_spam_words_and_symbols(self):
        raw = "*** L@@K WOW *** Sony WH-1000XM4 Headphones BEST PRICE FAST SHIPPING!"
        optimized = optimize_cassini_title(raw)
        assert "***" not in optimized
        assert "L@@K" not in optimized
        assert "WOW" not in optimized
        assert "BEST PRICE" not in optimized
        assert "Sony WH-1000XM4 Headphones" in optimized

    def test_backfills_high_traffic_aspects_within_80_chars(self):
        raw = "Sony WH-1000XM4 Wireless Headphones"
        specs = {
            "Brand": "Sony",
            "MPN": "WH1000XM4/B",
            "Color": "Black",
            "Department": "Unisex Adults"
        }
        optimized = optimize_cassini_title(raw, specifics=specs, condition="Used - Very Good")
        assert "WH1000XM4/B" in optimized
        assert "Black" in optimized
        assert "Used" in optimized
        assert len(optimized) <= 80

    def test_never_exceeds_80_chars(self):
        raw = "Patagonia Men's Better Sweater 1/4 Zip Fleece Jacket Stonewash Gray Size Large"
        specs = {
            "Brand": "Patagonia",
            "MPN": "25528",
            "Material": "100% Polyester Fleece",
            "Color": "Stonewash Gray",
            "Size": "L"
        }
        optimized = optimize_cassini_title(raw, specifics=specs, condition="Used - Excellent")
        assert len(optimized) <= 80
        assert not optimized.endswith((' ', '-', ',', '('))

    def test_handles_empty_or_none(self):
        assert optimize_cassini_title("") == ""
        assert optimize_cassini_title(None) == ""
