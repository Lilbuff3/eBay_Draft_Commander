"""
Listing Template Manager for eBay Draft Commander Pro
Save and load reusable listing configurations
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict


class ListingTemplate:
    """Represents a saved listing template"""
    
    def __init__(self, name: str, data: dict):
        self.name = name
        self.data = data
        self.created_at = data.get('_created_at', datetime.now().isoformat())
        self.updated_at = data.get('_updated_at', datetime.now().isoformat())
        self.use_count = data.get('_use_count', 0)
    
    def to_dict(self) -> dict:
        """Convert template to dictionary for saving"""
        result = self.data.copy()
        result['_name'] = self.name
        result['_created_at'] = self.created_at
        result['_updated_at'] = self.updated_at
        result['_use_count'] = self.use_count
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ListingTemplate':
        """Create template from saved dictionary"""
        name = data.pop('_name', 'Unnamed')
        return cls(name, data)


class TemplateManager:
    """Manages listing templates"""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize the template manager
        
        Args:
            templates_dir: Directory to store templates. Defaults to 'templates' in app dir.
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "data" / "templates"
        
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self._templates: Dict[str, ListingTemplate] = {}
        self.load_all()
    
    def load_all(self) -> Dict[str, ListingTemplate]:
        """Load all templates from disk"""
        self._templates = {}
        
        for file in self.templates_dir.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    template = ListingTemplate.from_dict(data)
                    self._templates[template.name] = template
            except Exception as e:
                print(f"Error loading template {file}: {e}")
        
        return self._templates
    
    def get_all(self) -> List[ListingTemplate]:
        """Get all templates sorted by use count (most used first)"""
        return sorted(self._templates.values(), 
                     key=lambda t: t.use_count, reverse=True)
    
    def get(self, name: str) -> Optional[ListingTemplate]:
        """Get a template by name"""
        return self._templates.get(name)
    
    def save(self, name: str, data: dict) -> ListingTemplate:
        """
        Save a new template or update existing
        
        Args:
            name: Template name
            data: Template data (condition, price, item_specifics, etc.)
            
        Returns:
            The saved template
        """
        # Check if updating existing
        if name in self._templates:
            template = self._templates[name]
            template.data = data
            template.updated_at = datetime.now().isoformat()
        else:
            template = ListingTemplate(name, data)
        
        self._templates[name] = template
        
        # Save to file
        filename = self._sanitize_filename(name) + ".json"
        filepath = self.templates_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template.to_dict(), f, indent=2)
        
        return template
    
    def delete(self, name: str) -> bool:
        """Delete a template"""
        if name not in self._templates:
            return False
        
        del self._templates[name]
        
        # Remove file
        filename = self._sanitize_filename(name) + ".json"
        filepath = self.templates_dir / filename
        
        if filepath.exists():
            filepath.unlink()
        
        return True
    
    def use(self, name: str) -> Optional[dict]:
        """
        Get template data and increment use count
        
        Args:
            name: Template name
            
        Returns:
            Template data dict (without metadata fields)
        """
        template = self._templates.get(name)
        if not template:
            return None
        
        # Increment use count
        template.use_count += 1
        template.data['_use_count'] = template.use_count
        
        # Save updated count
        self.save(template.name, template.data)
        
        # Return clean data (without metadata)
        return {k: v for k, v in template.data.items() if not k.startswith('_')}
    
    def get_names(self) -> List[str]:
        """Get list of all template names"""
        return [t.name for t in self.get_all()]
    
    def _sanitize_filename(self, name: str) -> str:
        """Convert template name to valid filename"""
        # Replace invalid characters
        invalid = '<>:"/\\|?*'
        result = name
        for char in invalid:
            result = result.replace(char, '_')
        return result[:50]  # Limit length
    
    def create_from_listing(self, name: str, listing_data: dict) -> ListingTemplate:
        """
        Create a template from listing data
        
        Args:
            name: Template name
            listing_data: Data from a created listing
            
        Returns:
            New template
        """
        # Extract reusable fields
        template_data = {
            'condition': listing_data.get('condition'),
            'default_price': listing_data.get('price'),
            'category_id': listing_data.get('category_id'),
            'item_specifics': listing_data.get('item_specifics', {}),
            'fulfillment_policy': listing_data.get('fulfillment_policy'),
            'payment_policy': listing_data.get('payment_policy'),
            'return_policy': listing_data.get('return_policy'),
        }
        
        # Remove None values
        template_data = {k: v for k, v in template_data.items() if v is not None}
        
        return self.save(name, template_data)


# Default templates for common categories
DEFAULT_TEMPLATES = [
    {
        'name': 'Electronics - Used Good',
        'condition': 'USED_GOOD',
        'default_price': '29.99',
        'item_specifics': {
            'Condition': 'Used',
        }
    },
    {
        'name': 'Electronics - Like New',
        'condition': 'LIKE_NEW',
        'default_price': '49.99',
        'item_specifics': {
            'Condition': 'Open box',
        }
    },
    {
        'name': 'Industrial Parts',
        'condition': 'USED_EXCELLENT',
        'default_price': '79.99',
        'item_specifics': {
            'Type': 'Replacement Part',
        }
    },
    {
        'name': 'Office Equipment',
        'condition': 'USED_GOOD',
        'default_price': '39.99',
        'item_specifics': {
            'Type': 'Office Equipment',
        }
    },
]


def get_template_manager() -> TemplateManager:
    """Get the global template manager instance"""
    global _instance
    if '_instance' not in globals():
        _instance = TemplateManager()
        
        # Create default templates if none exist
        if not _instance.get_all():
            for t in DEFAULT_TEMPLATES:
                name = t.pop('name')
                _instance.save(name, t)
    
    return _instance


# Test
if __name__ == "__main__":
    print("Testing Template Manager...")
    
    manager = TemplateManager()
    
    # Create a test template
    manager.save("Test Template", {
        'condition': 'USED_GOOD',
        'default_price': '25.00',
        'item_specifics': {'Brand': 'Test', 'Model': 'Demo'}
    })
    
    # List all
    print(f"\nTemplates: {manager.get_names()}")
    
    # Use a template
    data = manager.use("Test Template")
    print(f"\nTemplate data: {data}")
    
    print("\n✅ Template Manager working!")
