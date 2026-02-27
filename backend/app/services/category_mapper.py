"""
Category Mapper Service
Handles logic for determining the best eBay category for an item.
Wraps the lower-level ebay.taxonomy module and provides business logic/guards.
"""
from typing import Dict, Optional, Any
from backend.app.core.logger import get_logger
from backend.app.services.ebay.taxonomy import get_safe_category

logger = get_logger('category_mapper')

class CategoryMapper:
    def __init__(self):
        # Fallback category (Everything Else > Other)
        self.DEFAULT_CATEGORY_ID = "99" 
        
    def get_category(self, title: str, description: str = None) -> dict:
        """
        Determine the best category for an item based on title/description.
        
        Args:
            title: Item title
            description: Optional item description
            
        Returns:
            Dict containing:
            - id: Category ID (str)
            - name: Category Name (str)
            - source: How it was found ('ai', 'keyword_match', 'default')
            - warning: Optional warning message if a dangerous category was avoided
        """
        result = {
            'id': self.DEFAULT_CATEGORY_ID,
            'name': 'Everything Else > Other',
            'source': 'default',
            'warning': None
        }
        
        try:
            # delegated to existing taxonomy logic which likely has the "guards"
            cat_suggestion = get_safe_category(title)
            
            if cat_suggestion:
                result['id'] = cat_suggestion['id']
                result['name'] = cat_suggestion.get('name', 'Unknown')
                result['source'] = cat_suggestion.get('source', 'unknown')
                
                # Expose specific guards as warnings
                if 'guard_forced' in result['source']:
                    result['warning'] = f"Category forced to {result['name']} to avoid toner/restricted misclassification."
                    logger.info(f"Category Guard Triggered: {title} -> {result['name']}")
                else:
                    logger.debug(f"Category found: {result['name']} ({result['id']})")
                    
        except Exception as e:
            logger.error(f"Category lookup failed: {e}")
            # Fallback is already set in result
            
        return result
