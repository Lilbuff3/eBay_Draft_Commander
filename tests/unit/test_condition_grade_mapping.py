"""Category-aware condition ID mapping.

The generic CONDITION_ID_MAP sends USED_EXCELLENT as 3000, but in graded
categories (shoes, apparel, handbags) 3000 is "Pre-owned - Good" and Excellent
is a different id (2990). Map our condition grade to the category's actual
condition by display name so items are not silently down-graded.
"""
from backend.app.services.ebay.taxonomy import match_condition_by_grade

# Athletic Shoes (graded apparel set)
GRADED = [
    {"id": "1000", "name": "New with box"},
    {"id": "1500", "name": "New without box"},
    {"id": "1750", "name": "New with defects"},
    {"id": "2990", "name": "Pre-owned - Excellent"},
    {"id": "3000", "name": "Pre-owned - Good"},
    {"id": "3010", "name": "Pre-owned - Fair"},
]

# Electronics-style (no graded used tiers)
GENERIC = [
    {"id": "1000", "name": "New"},
    {"id": "1500", "name": "New other"},
    {"id": "3000", "name": "Used"},
    {"id": "7000", "name": "For parts or not working"},
]


def test_excellent_maps_to_2990_not_3000():
    assert match_condition_by_grade("USED_EXCELLENT", GRADED) == "2990"


def test_good_maps_to_3000():
    assert match_condition_by_grade("USED_GOOD", GRADED) == "3000"


def test_acceptable_maps_to_fair_3010():
    assert match_condition_by_grade("USED_ACCEPTABLE", GRADED) == "3010"


def test_very_good_degrades_to_good_when_no_very_good_tier():
    # No "Very Good" tier in apparel -> conservative down to Good, never up.
    assert match_condition_by_grade("USED_VERY_GOOD", GRADED) == "3000"


def test_like_new_prefers_excellent_when_no_like_new_tier():
    assert match_condition_by_grade("LIKE_NEW", GRADED) == "2990"


def test_excellent_returns_none_in_generic_category():
    # No "Excellent" display name -> None so caller uses generic fallback.
    assert match_condition_by_grade("USED_EXCELLENT", GENERIC) is None


def test_parts_maps_in_generic_category():
    assert match_condition_by_grade("FOR_PARTS_OR_NOT_WORKING", GENERIC) == "7000"


def test_unknown_enum_returns_none():
    assert match_condition_by_grade("MADE_UP", GRADED) is None


def test_empty_conditions_returns_none():
    assert match_condition_by_grade("USED_EXCELLENT", []) is None
