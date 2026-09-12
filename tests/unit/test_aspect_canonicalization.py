import pytest
from backend.app.services.listing_guardrails import (
    normalize_aspects,
    calculate_cassini_seo_score,
)

class TestAspectCanonicalization:
    def test_canonicalize_material_and_color(self):
        specs = {
            "Brand": "Nike",
            "Material": "cotton",
            "Color": "black",
            "Department": "mens",
        }
        normalized = normalize_aspects(specs)
        assert normalized["Material"] == "100% Cotton"
        assert normalized["Color"] == "Black"
        assert normalized["Department"] == "Men's"

    def test_unbranded_and_does_not_apply_normalization(self):
        specs = {
            "Brand": "Generic",
            "MPN": "N/A",
            "UPC": "unknown",
            "Model": "vintage",
        }
        normalized = normalize_aspects(specs)
        assert normalized["Brand"] == "Unbranded"
        assert normalized["MPN"] == "Does Not Apply"
        assert normalized["UPC"] == "Does Not Apply"
        assert normalized["Model"] == "Vintage"

    def test_drops_placeholder_junk(self):
        specs = {
            "Brand": "Sony",
            "Size": "Varies",
            "Features": "See description",
            "Color": "Black",
        }
        normalized = normalize_aspects(specs)
        assert "Size" not in normalized
        assert "Features" not in normalized
        assert normalized["Color"] == "Black"
        assert normalized["Brand"] == "Sony"


class TestCassiniSeoScore:
    def test_calculate_seo_score_with_schema(self):
        schema = [
            {"name": "Brand", "isRequired": True},
            {"name": "Type", "isRequired": True},
            {"name": "Color", "isRequired": False},
            {"name": "Material", "isRequired": False},
            {"name": "Department", "isRequired": False},
        ]
        specs = {
            "Brand": "Nike",
            "Type": "Sneaker",
            "Color": "Black",
            "Material": "Leather",
        }
        metrics = calculate_cassini_seo_score(specs, schema)
        assert metrics["required_total"] == 2
        assert metrics["required_filled"] == 2
        assert metrics["recommended_total"] == 3
        assert metrics["recommended_filled"] == 2
        assert metrics["seo_score"] > 80

    def test_calculate_seo_score_empty(self):
        metrics = calculate_cassini_seo_score({})
        assert metrics["seo_score"] == 0
        assert metrics["total_aspects_count"] == 0
