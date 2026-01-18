"""
Settings Manager for eBay Draft Commander Pro
Handles loading, saving, and validating application settings from .env file
"""
import os
from pathlib import Path
from typing import Optional


class SettingsManager:
    """Centralized settings management for the application"""
    
    # Default values for settings
    DEFAULTS = {
        'EBAY_ENVIRONMENT': 'production',
        'DEFAULT_CONDITION': 'USED_EXCELLENT',
        'DEFAULT_PRICE': '29.99',
        'AUTO_MOVE_POSTED': 'true',
    }
    
    # All known setting keys organized by category
    SETTING_CATEGORIES = {
        'eBay API': [
            'EBAY_APP_ID',
            'EBAY_DEV_ID', 
            'EBAY_CERT_ID',
            'EBAY_RU_NAME',
            'EBAY_ENVIRONMENT',
        ],
        'eBay Tokens': [
            'EBAY_USER_TOKEN',
            'EBAY_REFRESH_TOKEN',
        ],
        'Business Policies': [
            'EBAY_FULFILLMENT_POLICY',
            'EBAY_PAYMENT_POLICY',
            'EBAY_RETURN_POLICY',
            'EBAY_MERCHANT_LOCATION',
        ],
        'AI Settings': [
            'GOOGLE_API_KEY',
        ],
        'Application': [
            'DEFAULT_CONDITION',
            'DEFAULT_PRICE',
            'AUTO_MOVE_POSTED',
        ],
    }
    
    # Required settings that must have values
    REQUIRED = [
        'EBAY_APP_ID',
        'EBAY_CERT_ID',
        'EBAY_USER_TOKEN',
    ]
    
    # Sensitive settings that should be masked in UI
    SENSITIVE = [
        'EBAY_USER_TOKEN',
        'EBAY_REFRESH_TOKEN',
        'GOOGLE_API_KEY',
        'EBAY_CERT_ID',
    ]
    
    def __init__(self, env_path: Optional[Path] = None):
        """
        Initialize the settings manager
        
        Args:
            env_path: Path to .env file. Defaults to .env in same directory as this file.
        """
        if env_path is None:
            env_path = Path(__file__).parent / ".env"
        self.env_path = Path(env_path)
        self._settings = {}
        self._comments = []  # Preserve comments from original file
        self.load()
    
    def load(self) -> dict:
        """
        Load settings from .env file
        
        Returns:
            Dictionary of all settings
        """
        self._settings = {}
        self._comments = []
        
        if not self.env_path.exists():
            # Create empty file with defaults
            self._settings = self.DEFAULTS.copy()
            return self._settings
        
        with open(self.env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Preserve comments and blank lines
                if not line or line.startswith('#'):
                    self._comments.append(line)
                    continue
                
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    self._settings[key] = value
        
        # Apply defaults for missing settings
        for key, default in self.DEFAULTS.items():
            if key not in self._settings:
                self._settings[key] = default
        
        return self._settings
    
    def save(self, settings: Optional[dict] = None) -> None:
        """
        Save settings to .env file
        
        Args:
            settings: Dictionary of settings to save. If None, saves current settings.
        """
        if settings is not None:
            self._settings.update(settings)
        
        lines = []
        
        # Write header comment
        lines.append("# eBay API Credentials")
        lines.append("# Application: Image Lister (Production)")
        lines.append("# Keep this file secure - do not share or commit to version control")
        lines.append("")
        
        # Group settings by category
        written_keys = set()
        
        for category, keys in self.SETTING_CATEGORIES.items():
            category_has_values = any(
                self._settings.get(key) for key in keys
            )
            
            if category_has_values:
                # Add section comment
                lines.append(f"# {category}")
                
                for key in keys:
                    value = self._settings.get(key, '')
                    if value:
                        lines.append(f"{key}={value}")
                        written_keys.add(key)
                
                lines.append("")
        
        # Write any remaining settings not in categories
        for key, value in self._settings.items():
            if key not in written_keys and value:
                lines.append(f"{key}={value}")
        
        # Write to file
        with open(self.env_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a setting value
        
        Args:
            key: Setting key
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        return self._settings.get(key, default or self.DEFAULTS.get(key))
    
    def set(self, key: str, value: str) -> None:
        """
        Set a setting value (in memory, call save() to persist)
        
        Args:
            key: Setting key
            value: Setting value
        """
        self._settings[key] = value
    
    def get_all(self) -> dict:
        """
        Get all settings
        
        Returns:
            Dictionary of all settings
        """
        return self._settings.copy()
    
    def validate(self) -> list:
        """
        Validate settings and return list of errors
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        for key in self.REQUIRED:
            if not self._settings.get(key):
                errors.append(f"Missing required setting: {key}")
        
        # Validate specific formats
        if self._settings.get('DEFAULT_PRICE'):
            try:
                price = float(self._settings['DEFAULT_PRICE'])
                if price < 0:
                    errors.append("Default price cannot be negative")
            except ValueError:
                errors.append("Default price must be a valid number")
        
        return errors
    
    def is_sensitive(self, key: str) -> bool:
        """
        Check if a setting is sensitive (should be masked)
        
        Args:
            key: Setting key
            
        Returns:
            True if sensitive
        """
        return key in self.SENSITIVE
    
    def get_category(self, key: str) -> Optional[str]:
        """
        Get the category for a setting key
        
        Args:
            key: Setting key
            
        Returns:
            Category name or None
        """
        for category, keys in self.SETTING_CATEGORIES.items():
            if key in keys:
                return category
        return None
    
    def get_all_keys(self) -> list:
        """
        Get all known setting keys in order
        
        Returns:
            List of all setting keys
        """
        keys = []
        for category_keys in self.SETTING_CATEGORIES.values():
            keys.extend(category_keys)
        return keys


# Singleton instance
_instance = None


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance"""
    global _instance
    if _instance is None:
        _instance = SettingsManager()
    return _instance


if __name__ == "__main__":
    # Test the settings manager
    print("Testing Settings Manager...")
    
    manager = SettingsManager()
    settings = manager.load()
    
    print(f"\nLoaded {len(settings)} settings from {manager.env_path}")
    print("\nSettings by category:")
    
    for category, keys in SettingsManager.SETTING_CATEGORIES.items():
        print(f"\n{category}:")
        for key in keys:
            value = manager.get(key, "(not set)")
            if manager.is_sensitive(key) and value != "(not set)":
                # Mask sensitive values
                value = value[:10] + "..." if len(value) > 10 else "***"
            print(f"  {key}: {value}")
    
    # Validate
    errors = manager.validate()
    if errors:
        print("\n⚠️ Validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✅ All settings valid")
