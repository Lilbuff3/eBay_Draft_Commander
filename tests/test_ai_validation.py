
import pytest
import json
from unittest.mock import MagicMock, patch
from backend.app.services.ai_analyzer import AIAnalyzer

@pytest.fixture
def analyzer():
    """Create AIAnalyzer instance without initializing real GenAI client"""
    with patch('google.genai.Client'):
        ai = AIAnalyzer()
        # Mock encode_image to avoid file system dependency
        ai.encode_image = MagicMock(return_value="dummy_base64")
        return ai

@pytest.fixture(autouse=True)
def mock_pil_open():
    """Mock PIL Image.open so fake paths don't fail the image validation check"""
    mock_img = MagicMock()
    with patch('PIL.Image.open', return_value=mock_img):
        yield

def test_valid_ai_response(analyzer):
    """Test that valid properly structured response is accepted"""
    valid_data = {
        "identification": {
            "brand": "Sony",
            "model": "A9 III",
            "mpn": "ILCE-9M3",
            "confidence_score": 95
        },
        "condition": {
            "state": "New",
            "wear_details": "Pristine"
        },
        "listing": {
            "suggested_title": "Sony Alpha 9 III Digital Camera",
            "suggested_price": 5998.00
        }
    }
    
    # Mocking the internal _analyze_item response text parsing part
    mock_response = MagicMock()
    mock_response.text = json.dumps(valid_data)
    analyzer.client.models.generate_content.return_value = mock_response
    
    result = analyzer.analyze_item(["fake/path.jpg"])
    
    assert "error" not in result
    assert result["identification"]["brand"] == "Sony"
    assert result["listing"]["suggested_price"] == 5998.00

def test_missing_required_keys(analyzer):
    """Test that missing required keys (identification/listing) triggers error"""
    invalid_data = {
        "identification": {"brand": "Test"},
        # "listing" is missing
        "condition": {"state": "Used"}
    }
    
    mock_response = MagicMock()
    mock_response.text = json.dumps(invalid_data)
    analyzer.client.models.generate_content.return_value = mock_response
    
    result = analyzer.analyze_item(["fake/path.jpg"])
    
    assert "error" in result
    assert "missing required keys" in result["error"]
    assert "listing" in result["error"]

def test_invalid_data_types(analyzer):
    """Test that non-dict values for required keys trigger error"""
    invalid_data = {
        "identification": "Not A Dict",
        "listing": {"suggested_title": "Test"}
    }
    
    mock_response = MagicMock()
    mock_response.text = json.dumps(invalid_data)
    analyzer.client.models.generate_content.return_value = mock_response
    
    result = analyzer.analyze_item(["fake/path.jpg"])
    
    assert "error" in result
    assert "Invalid 'identification' structure" in result["error"]

def test_partial_data_returned_on_missing_keys(analyzer):
    """Test that partial data is returned even when validation fails"""
    invalid_data = {
        "identification": {"brand": "Test"},
        "some_other_key": "data"
    }
    
    mock_response = MagicMock()
    mock_response.text = json.dumps(invalid_data)
    analyzer.client.models.generate_content.return_value = mock_response
    
    result = analyzer.analyze_item(["fake/path.jpg"])
    
    assert "error" in result
    assert "partial_data" in result
    assert result["partial_data"]["identification"]["brand"] == "Test"

def test_json_parsing_resilience(analyzer):
    """Test that analyzer can extract JSON from markdown or messy text"""
    messy_text = "Here is the response: ```json\n{\"identification\": {\"brand\": \"Sony\"}, \"listing\": {\"suggested_title\": \"Test\"}}\n``` Hope this helps!"
    
    mock_response = MagicMock()
    mock_response.text = messy_text
    analyzer.client.models.generate_content.return_value = mock_response
    
    result = analyzer.analyze_item(["fake/path.jpg"])
    
    assert "error" not in result
    assert result["identification"]["brand"] == "Sony"
