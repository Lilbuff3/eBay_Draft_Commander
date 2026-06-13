"""Tests for backfilling required eBay aspects from listing text.

The AI pipeline often extracts niche specifics (heel height, materials) but
misses the basic required aspects (Size, Color, Department) that are sitting
in the title. This backfill fills them from the title against each aspect's
own allowed-value list, so the listing is not needlessly routed to review.
"""
from backend.app.services.processor_service import ProcessorService

backfill = ProcessorService._backfill_aspects_from_text


def _aspect(name, values):
    return {"name": name, "values": values, "isRequired": True}


SHOE_ASPECTS = [
    _aspect("US Shoe Size", ["8", "8.5", "9", "9.5", "10", "10.5", "19.5"]),
    _aspect("Color", ["Black", "White", "Red", "Multicolor"]),
    _aspect("Department", ["Men", "Women", "Unisex Adults"]),
]

TITLE = "Nike Romaleos 4 CD3463-010 Black White Weightlifting Shoes Men's Size 9.5 Used"


def test_fills_size_color_department_from_title():
    specifics = {"Brand": "Nike"}
    filled = backfill(SHOE_ASPECTS, specifics, TITLE)
    assert specifics["US Shoe Size"] == "9.5"
    assert specifics["Color"] == "Black"      # earliest color word wins (dominant)
    assert specifics["Department"] == "Men"   # matches "Men's"
    assert {"US Shoe Size", "Color", "Department"} <= {n for n, _ in filled}


def test_size_ignores_model_number_before_size_cue():
    # "Romaleos 4" is a model number; the real size is "9.5" after "Size".
    # Must not grab the stray '4'.
    specifics = {}
    backfill([_aspect("US Shoe Size", ["4", "9.5"])], specifics, TITLE)
    assert specifics["US Shoe Size"] == "9.5"


def test_size_not_filled_without_size_cue():
    # No "size" cue word -> don't guess a bare number (likely a model code).
    specifics = {}
    backfill([_aspect("US Shoe Size", ["4", "9.5"])], specifics, "Nike Romaleos 4 CD3463-010 Shoes")
    assert "US Shoe Size" not in specifics


def test_does_not_overwrite_existing_values():
    specifics = {"Color": "Red"}
    backfill(SHOE_ASPECTS, specifics, TITLE)
    assert specifics["Color"] == "Red"


def test_numeric_size_not_confused_by_substring():
    # title has 9.5; must not match 19.5 (substring) nor partial
    specifics = {}
    backfill([_aspect("US Shoe Size", ["5", "9.5", "19.5"])], specifics, TITLE)
    assert specifics["US Shoe Size"] == "9.5"


def test_size_10_not_matched_inside_10_5():
    specifics = {}
    backfill([_aspect("US Shoe Size", ["10", "10.5"])], specifics, "Mens Size 10.5 Sneaker")
    assert specifics["US Shoe Size"] == "10.5"


def test_department_men_not_matched_inside_women():
    specifics = {}
    backfill([_aspect("Department", ["Men", "Women"])], specifics, "Womens Running Shoe")
    assert specifics["Department"] == "Women"


def test_no_match_leaves_aspect_missing():
    specifics = {}
    filled = backfill([_aspect("Color", ["Teal", "Maroon"])], specifics, TITLE)
    assert "Color" not in specifics
    assert filled == []


def test_aspect_without_values_is_skipped():
    specifics = {}
    backfill([{"name": "Custom Bundle", "isRequired": True}], specifics, TITLE)
    assert "Custom Bundle" not in specifics


def test_multiword_value_matches_whole_phrase():
    specifics = {}
    backfill([_aspect("Department", ["Men", "Unisex Adults"])], specifics, "Unisex Adults trail runner")
    assert specifics["Department"] == "Unisex Adults"
