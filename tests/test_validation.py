
import pytest
from pathlib import Path
from backend.app.core.validator import (
    validate_price, validate_title, validate_isbn, 
    validate_safe_path, validate_condition, ValidationError
)

def test_price_validation():
    assert validate_price("10.50") == 10.50
    assert validate_price(25) == 25.00
    assert validate_price("0") == 0.00
    
    with pytest.raises(ValidationError) as exc:
        validate_price("-1")
    assert "cannot be negative" in str(exc.value)
    
    with pytest.raises(ValidationError):
        validate_price("abc")
        
    with pytest.raises(ValidationError):
        validate_price("60000")

def test_title_validation():
    assert validate_title("Valid Title") == "Valid Title"
    assert validate_title("  Trimmed Title  ") == "Trimmed Title"
    
    with pytest.raises(ValidationError) as exc:
        validate_title("A" * 81)
    assert "exceeds eBay 80-character limit" in str(exc.value)
    
    with pytest.raises(ValidationError):
        validate_title("Too") # Min 4 chars

def test_isbn_validation():
    assert validate_isbn("978-3-16-148410-0") == "9783161484100"
    assert validate_isbn("0306406152") == "0306406152"
    assert validate_isbn("123456789X") == "123456789X"
    
    with pytest.raises(ValidationError):
        validate_isbn("123")
        
    with pytest.raises(ValidationError):
        validate_isbn("abcdefghij")

def test_condition_validation():
    assert validate_condition("new") == "NEW"
    assert validate_condition("New Old Stock") == "NEW_OTHER"
    assert validate_condition("Used - Excellent") == "USED_EXCELLENT"
    assert validate_condition("") == "USED_GOOD" # Default
    
    with pytest.raises(ValidationError):
        validate_condition("Broken")

def test_path_validation(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    item = inbox / "my_item"
    item.mkdir()
    
    # Valid child path
    assert validate_safe_path(str(item), base_dir=inbox) == item.resolve()
    
    # Attempted traversal
    outside = tmp_path / "private"
    outside.mkdir()
    
    with pytest.raises(ValidationError) as exc:
        validate_safe_path(str(outside), base_dir=inbox)
    assert "Access denied" in str(exc.value)
    
    # Traversal via ..
    traversal = inbox / ".." / "private"
    with pytest.raises(ValidationError):
        validate_safe_path(str(traversal), base_dir=inbox)
