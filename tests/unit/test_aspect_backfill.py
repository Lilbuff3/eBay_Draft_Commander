"""Tests for aspect backfilling from text and research specs mapping."""
import pytest
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


APPAREL_SIZE = ["S", "M", "L", "XL", "XXL", "Small", "Medium", "Large", "X-Large", "2XS"]


def test_word_size_filled_from_title():
    # Apparel sizes are spelled-out words ("Large"), never preceded by a "Size" cue.
    # The numeric-cue rule misses them, so they must be matched as whole title tokens.
    specifics = {}
    backfill([_aspect("Size", APPAREL_SIZE)], specifics,
             "ST. JOHN'S BAY Men's Large Light Wash Denim Button Down Shirt Blue")
    assert specifics["Size"] == "Large"


def test_word_size_abbreviation_filled():
    specifics = {}
    backfill([_aspect("Size", APPAREL_SIZE)], specifics, "Carhartt Mens XL Hoodie")
    assert specifics["Size"] == "XL"


def test_word_size_fallback_never_grabs_bare_number():
    # Regression guard: the word-size fallback must NOT match a bare numeric value
    # without a size cue (that number is usually a model/style code).
    specifics = {}
    backfill([_aspect("Size", ["4", "9.5", "Large"])], specifics, "Nike Romaleos 9.5 Blue")
    assert "Size" not in specifics


def test_word_size_does_not_false_match_single_letter():
    # A stray single-letter value (S/M/L) must not match random words in the title.
    specifics = {}
    backfill([_aspect("Size", ["S", "M", "L"])], specifics, "Slim Mens Leather Belt")
    assert "Size" not in specifics


@pytest.fixture
def service():
    return ProcessorService()


class TestAspectBackfillFromText:
    """Test optimized O(1) backfilling of aspects from text."""

    def test_backfill_brand_from_title(self, service):
        aspect_schema = [
            {"name": "Brand", "isRequired": True, "values": ["Xerox", "Dell", "HP"]}
        ]
        specifics = {}
        text = "Genuine Xerox 108R00713 Solid Ink"
        
        filled = service._backfill_aspects_from_text(aspect_schema, specifics, text)
        
        assert specifics.get("Brand") == "Xerox"
        assert ("Brand", "Xerox") in filled

    def test_backfill_longer_match_priority(self, service):
        aspect_schema = [
            {"name": "Brand", "isRequired": True, "values": ["Sony", "Sony PlayStation", "PlayStation"]}
        ]
        specifics = {}
        # Title has "Sony PlayStation 5 Console"
        text = "Sony PlayStation 5 Console"
        
        service._backfill_aspects_from_text(aspect_schema, specifics, text)
        
        # Should prefer "Sony PlayStation" (longer match starting at the same word index)
        assert specifics.get("Brand") == "Sony PlayStation"

    def test_backfill_possessive_stripping(self, service):
        aspect_schema = [
            {"name": "Department", "isRequired": True, "values": ["Men", "Women", "Unisex"]}
        ]
        specifics = {}
        text = "Men's Blue Denim Shirt"
        
        service._backfill_aspects_from_text(aspect_schema, specifics, text)
        
        assert specifics.get("Department") == "Men"

    def test_backfill_does_not_overwrite_existing(self, service):
        aspect_schema = [
            {"name": "Brand", "isRequired": True, "values": ["Dell", "HP"]}
        ]
        specifics = {"Brand": "Dell"}
        text = "HP Latitude Laptop"
        
        service._backfill_aspects_from_text(aspect_schema, specifics, text)
        
        # Brand should remain "Dell" (no overwrite)
        assert specifics.get("Brand") == "Dell"

    def test_backfill_size_regex_rules(self, service):
        aspect_schema = [
            {"name": "US Shoe Size", "isRequired": True, "values": ["9", "9.5", "10"]}
        ]
        # Case A: Bare number in title should NOT be backfilled (could be model code)
        specifics_a = {}
        text_a = "Nike Romaleos 9.5 Blue"
        service._backfill_aspects_from_text(aspect_schema, specifics_a, text_a)
        assert "US Shoe Size" not in specifics_a

        # Case B: Size following cue word "Size" or "Sz" SHOULD be backfilled
        specifics_b = {}
        text_b = "Nike Romaleos Size 9.5 Blue"
        service._backfill_aspects_from_text(aspect_schema, specifics_b, text_b)
        assert specifics_b.get("US Shoe Size") == "9.5"


class TestResearchSpecsMapper:
    """Test programmatic mapping of web research specs to eBay aspects."""

    def test_map_research_specs_allowed_values(self, service):
        aspect_schema = [
            {"name": "Color", "values": ["Red", "Blue", "Green"]}
        ]
        specifics = {}
        research_specs = {"color": "blue"}  # lowercase -> matches Blue
        
        service._map_research_specs_to_aspects(aspect_schema, specifics, research_specs)
        
        assert specifics.get("Color") == "Blue"

    def test_map_research_specs_free_text(self, service):
        aspect_schema = [
            {"name": "Voltage", "values": []}  # Free text aspect
        ]
        specifics = {}
        research_specs = {"voltage": "120 V"}
        
        service._map_research_specs_to_aspects(aspect_schema, specifics, research_specs)
        
        assert specifics.get("Voltage") == "120 V"

    def test_map_research_specs_key_normalization(self, service):
        aspect_schema = [
            {"name": "Memory Type", "values": ["DDR3", "DDR4"]}
        ]
        specifics = {}
        research_specs = {"memory_type": "DDR4"}  # memory_type -> matches Memory Type
        
        service._map_research_specs_to_aspects(aspect_schema, specifics, research_specs)
        
        assert specifics.get("Memory Type") == "DDR4"

    def test_map_research_specs_no_overwrite(self, service):
        aspect_schema = [
            {"name": "Color", "values": ["Red", "Blue", "Green"]}
        ]
        specifics = {"Color": "Red"}
        research_specs = {"color": "Blue"}
        
        service._map_research_specs_to_aspects(aspect_schema, specifics, research_specs)
        
        assert specifics.get("Color") == "Red"

    def test_backfill_department_men_from_title(self, service):
        """Test a men's title sets Department to Men."""
        aspect_schema = [
            {"name": "Department", "isRequired": True, "values": ["Men", "Women", "Unisex"]}
        ]
        specifics = {}
        # Simulate backfill_text containing the product_type "Men's Shoes"
        text = "Nike Air Max Men's Shoes"
        service._backfill_aspects_from_text(aspect_schema, specifics, text)
        assert specifics.get("Department") == "Men"

    def test_backfill_ambiguous_title_no_department(self, service):
        """Test an ambiguous title leaves Department absent."""
        aspect_schema = [
            {"name": "Department", "isRequired": True, "values": ["Men", "Women", "Unisex"]}
        ]
        specifics = {}
        text = "Nike Air Max Running Shoes"
        service._backfill_aspects_from_text(aspect_schema, specifics, text)
        assert "Department" not in specifics

    def test_optional_aspects_are_skipped_in_backfill(self, service):
        """Test that an optional aspect with allowed values in the title is NOT auto-filled."""
        aspect_schema = [
            {"name": "Theme", "isRequired": False, "values": ["Classic", "Modern", "Retro"]},
            {"name": "Department", "isRequired": True, "values": ["Men", "Women"]}
        ]
        specifics = {}
        text = "Classic Men's Shoes Retro Style"
        
        service._backfill_aspects_from_text(aspect_schema, specifics, text)
        
        # Required aspect was filled
        assert specifics.get("Department") == "Men"
        # Optional aspects were skipped even though 'Classic' and 'Retro' are in text
        assert "Theme" not in specifics
