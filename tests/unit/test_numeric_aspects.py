"""Tests for NUMBER-typed eBay item-specific sanitization.

eBay Trading API rejects a listing (error 21919323, e.g. "Fabric weight must be
greater than 0. Use up to 1 decimal digit.") when an item specific whose category
schema dataType is NUMBER carries a non-numeric value such as
"Mid-weight (approx. 7-8 oz)". `sanitize_numeric_aspects` coerces a clean positive
number or drops the aspect so the listing never fails on this.
"""
from backend.app.services.processor_service import sanitize_numeric_aspects


SCHEMA = [
    {"name": "Fabric Weight", "type": "NUMBER"},
    {"name": "Unit Quantity", "type": "NUMBER"},
    {"name": "Brand", "type": "STRING"},
]


def test_drops_descriptive_text_for_number_aspect():
    specifics = {"Fabric Weight": "Mid-weight (approx. 7-8 oz)", "Brand": "L.L.Bean"}
    sanitize_numeric_aspects(specifics, SCHEMA)
    assert "Fabric Weight" not in specifics
    assert specifics["Brand"] == "L.L.Bean"


def test_coerces_clean_number_with_unit():
    specifics = {"Fabric Weight": "7.5 oz"}
    sanitize_numeric_aspects(specifics, SCHEMA)
    assert specifics["Fabric Weight"] == "7.5"


def test_keeps_plain_integer_as_integer_string():
    specifics = {"Unit Quantity": "12"}
    sanitize_numeric_aspects(specifics, SCHEMA)
    assert specifics["Unit Quantity"] == "12"


def test_drops_zero_value():
    specifics = {"Fabric Weight": "0"}
    sanitize_numeric_aspects(specifics, SCHEMA)
    assert "Fabric Weight" not in specifics


def test_drops_range_value():
    specifics = {"Fabric Weight": "7-8 oz"}
    sanitize_numeric_aspects(specifics, SCHEMA)
    assert "Fabric Weight" not in specifics


def test_drops_does_not_apply_for_number_aspect():
    specifics = {"Fabric Weight": "Does Not Apply"}
    sanitize_numeric_aspects(specifics, SCHEMA)
    assert "Fabric Weight" not in specifics


def test_leaves_string_aspect_untouched():
    specifics = {"Brand": "Mid-weight (approx. 7-8 oz)"}
    sanitize_numeric_aspects(specifics, SCHEMA)
    assert specifics["Brand"] == "Mid-weight (approx. 7-8 oz)"


def test_handles_list_value():
    specifics = {"Fabric Weight": ["7.5 oz"]}
    sanitize_numeric_aspects(specifics, SCHEMA)
    assert specifics["Fabric Weight"] == "7.5"


def test_rounds_to_one_decimal():
    specifics = {"Fabric Weight": "7.567 oz"}
    sanitize_numeric_aspects(specifics, SCHEMA)
    assert specifics["Fabric Weight"] == "7.6"


def test_empty_schema_is_noop():
    specifics = {"Fabric Weight": "whatever"}
    sanitize_numeric_aspects(specifics, [])
    assert specifics["Fabric Weight"] == "whatever"


def test_logs_when_dropping():
    logs = []
    specifics = {"Fabric Weight": "Mid-weight"}
    sanitize_numeric_aspects(specifics, SCHEMA, log=lambda m: logs.append(m))
    assert any("Fabric Weight" in m for m in logs)
