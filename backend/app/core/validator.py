"""
Centralized validation logic for eBay Draft Commander.
Ensures data integrity and security for API and service layers.
"""
import re
from pathlib import Path
from flask import current_app

class ValidationError(Exception):
    """Custom exception for validation failures"""
    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field

def validate_price(price):
    """
    Ensure price is a valid positive number.
    Accepts string, int, or float.
    Returns: float
    """
    try:
        val = float(price)
        if val < 0:
            raise ValidationError("Price cannot be negative", "price")
        # Optional: Max price sanity check
        if val > 50000:
            raise ValidationError("Price exceeds maximum sanity limit ($50,000)", "price")
        return round(val, 2)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid price format: {price}", "price")

def validate_title(title):
    """
    Ensure title meets eBay requirements (max 80 chars).
    """
    if not title:
        raise ValidationError("Title is required", "title")
    
    title = str(title).strip()
    if len(title) > 80:
        raise ValidationError(f"Title exceeds eBay 80-character limit ({len(title)} chars)", "title")
    
    if len(title) < 4:
        raise ValidationError("Title is too short (min 4 chars)", "title")
        
    return title

def validate_isbn(isbn):
    """
    Validate ISBN-10 or ISBN-13 format.
    """
    if not isbn:
        return None
        
    # Remove hyphens and spaces
    clean_isbn = re.sub(r'[\s\-]', '', str(isbn))
    
    if len(clean_isbn) not in [10, 13]:
        raise ValidationError("ISBN must be 10 or 13 digits", "isbn")
        
    if not clean_isbn.isdigit() and not (len(clean_isbn) == 10 and clean_isbn[-1].upper() == 'X'):
         raise ValidationError("Invalid characters in ISBN", "isbn")
         
    return clean_isbn

def validate_safe_path(path_str, base_dir=None):
    """
    Ensure path is within an authorized directory to prevent path traversal.
    """
    if not path_str:
        raise ValidationError("Path is required", "path")
        
    if base_dir is None:
        # Fallback to INBOX_DIR if in Flask context
        try:
            base_dir = Path(current_app.config['INBOX_DIR']).resolve()
        except:
            raise ValidationError("Base directory for path validation not configured", "path")
    else:
        base_dir = Path(base_dir).resolve()
        
    try:
        requested_path = Path(path_str).resolve()
        # Check if requested_path is exactly base_dir or a child of it
        if not str(requested_path).startswith(str(base_dir)):
            raise ValidationError(f"Security: Access denied to path outside of authorized root", "path")
        return requested_path
    except Exception as e:
        raise ValidationError(f"Invalid path: {e}", "path")

def validate_condition(condition):
    """
    Check against allowed eBay condition strings.
    """
    allowed = {
        'NEW', 'NEW_OTHER', 'NEW_WITH_DEFECTS', 
        'USED_EXCELLENT', 'USED_VERY_GOOD', 'USED_GOOD', 'USED_ACCEPTABLE', 'FOR_PARTS_OR_NOT_WORKING'
    }
    
    if not condition:
        return 'USED_GOOD' # Default fallback
        
    # Standardize: uppercase and remove non-alphanumeric (keep underscores)
    cond_norm = re.sub(r'[^A-Z0-9_]', '', str(condition).upper().replace('-', '_').replace(' ', '_'))
    # Remove duplicate underscores
    cond_norm = re.sub(r'_+', '_', cond_norm).strip('_')
    
    # Map friendly names to eBay constants
    mapping = {
        'NEW_OLD_STOCK': 'NEW_OTHER',
        'NEW_OPEN_BOX': 'NEW_OTHER',
        'LIKE_NEW': 'USED_EXCELLENT',
        'VERY_GOOD': 'USED_VERY_GOOD',
        'GOOD': 'USED_GOOD',
        'ACCEPTABLE': 'USED_ACCEPTABLE',
        'PARTS': 'FOR_PARTS_OR_NOT_WORKING',
        'FOR_PARTS': 'FOR_PARTS_OR_NOT_WORKING',
        'NOT_WORKING': 'FOR_PARTS_OR_NOT_WORKING',
        'USED': 'USED_GOOD',
    }
    
    final_cond = mapping.get(cond_norm, cond_norm)
    
    if final_cond not in allowed:
         raise ValidationError(f"Invalid condition: {condition}. Must be one of: {', '.join(allowed)}", "condition")
         
    return final_cond
