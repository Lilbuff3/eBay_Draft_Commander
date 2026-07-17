"""
Settings Manager for eBay Draft Commander Pro
Handles loading, saving, and validating application settings from .env file
"""
import os
import threading
from pathlib import Path
from typing import Optional
from backend.app.core.logger import get_logger

logger = get_logger('settings_manager')


class SettingsManager:
    """Centralized settings management for the application"""
    
    # Default values for settings
    DEFAULTS = {
        'EBAY_ENVIRONMENT': 'production',
        'DEFAULT_CONDITION': 'USED_EXCELLENT',
        'DEFAULT_PRICE': '29.99',
        'AUTO_MOVE_POSTED': 'true',
        'AUTO_PUBLISH': 'true',  # If false, creates drafts instead of live listings
        'CONFIDENCE_THRESHOLD': '85',  # 0-100: minimum AI confidence to auto-publish
        'AUTO_PUBLISH_MIN_PRICE': '10.00',  # Minimum price to auto-publish (force review below)
        'FAST_MODE': 'false',  # Skip Phase 2 web research + Gemini pricing grounding (5-13s/item faster)
        'ESTIMATED_SHIPPING_COST': '6.50',  # Baked into price for free-shipping listings
        'ENABLE_BACKGROUND_REMOVAL': 'false',  # rembg background removal (off for MVP)
        'PROMOTED_LISTINGS_ENABLED': 'false',
        'PROMOTED_LISTINGS_AD_RATE': '5.0',
        'SOURCING_MIN_PROFIT': '5.00',   # Min $ profit for a BUY verdict on the Source tab
        'SOURCING_ROI_MULTIPLE': '3.0',  # Pay at most net_proceeds / this (3x rule)
        'SOURCING_SHIP_COST': '5.00',    # Est. actual ship cost when sourcing (Media Mail-ish)
        'PRICE_AGREEMENT_RATIO': '1.6',  # Comps vs AI cross-check: further apart = conflict -> review
        'ACTIVE_TO_SOLD_FACTOR': '0.87', # Active-comp -> est. sold discount (restart to apply; tune via tools/accuracy_benchmark.py --suggest-factor)
        'WHATSAPP_NOTIFY_CHAT_ID': '',   # Owner chat for review/summary texts (empty = off)
        'BEST_OFFER_ENABLED': 'true',        # Add Best Offer to every new listing
        'BEST_OFFER_AUTO_ACCEPT_PCT': '90',  # Auto-accept offers >= this % of list price
        'BEST_OFFER_AUTO_DECLINE_PCT': '60', # Auto-decline offers < this % of list price
        'PRICE_DISCOVERY_ENABLED': 'true',   # No-comp items: list high + Best Offer instead of review
        'PRICE_DISCOVERY_MARKUP_PCT': '25',  # Discovery list price = suggested * (1 + this%)
        'PRICE_DISCOVERY_DECLINE_PCT': '50', # Aggressive auto-decline floor for discovery listings
        # Autopilot (daily offers-to-watchers + stale markdown ladder + relist)
        'OFFERS_ENABLED': 'true',            # Send offers to watchers
        'OFFER_DISCOUNT_PCT': '10',          # Offer discount % off current price
        'OFFER_MIN_WATCHERS': '1',           # Min watchers before an offer is sent
        'MARKDOWN_ENABLED': 'true',          # Stale-item markdown ladder
        'MARKDOWN_AFTER_DAYS': '14',         # First markdown after N live days (also step spacing)
        'MARKDOWN_STEP_PCT': '5',            # Each step drops this % off current price
        'MARKDOWN_FLOOR_PCT': '70',          # Never below this % of original price
        'OFFERS_MARKDOWNS_DRY_RUN': 'true',  # Log-only until the owner flips live
        'DISCOVERY_MARKDOWN_AFTER_DAYS': '7',   # Aggressive ladder for price-discovery items
        'DISCOVERY_MARKDOWN_STEP_PCT': '10',
        'DISCOVERY_MARKDOWN_FLOOR_PCT': '40',
        'AUTOPILOT_RUN_HOUR': '9',           # Local hour the daily cycle fires
        'RELIST_ENABLED': 'true',            # Relist unsold listings (one markdown step applied)
        'RELIST_MAX_TIMES': '3',             # Max automatic relists per listing
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
            'EBAY_POSTAL_CODE',
        ],
        'AI Settings': [
            'GOOGLE_API_KEY',
            'GEMINI_RPM_LIMIT',
        ],
        'Automation': [
            'AUTO_PUBLISH',
            'CONFIDENCE_THRESHOLD',
            'AUTO_PUBLISH_MIN_PRICE',
            'FAST_MODE',
            'PROMOTED_LISTINGS_ENABLED',
            'PROMOTED_LISTINGS_AD_RATE',
            'PRICE_AGREEMENT_RATIO',
            'ACTIVE_TO_SOLD_FACTOR',
            'WHATSAPP_NOTIFY_CHAT_ID',
            'BEST_OFFER_ENABLED',
            'BEST_OFFER_AUTO_ACCEPT_PCT',
            'BEST_OFFER_AUTO_DECLINE_PCT',
            'PRICE_DISCOVERY_ENABLED',
            'PRICE_DISCOVERY_MARKUP_PCT',
            'PRICE_DISCOVERY_DECLINE_PCT',
        ],
        'Application': [
            'DEFAULT_CONDITION',
            'DEFAULT_PRICE',
            'AUTO_MOVE_POSTED',
            'ESTIMATED_SHIPPING_COST',
            'ENABLE_BACKGROUND_REMOVAL',
        ],
        'Sourcing': [
            'SOURCING_MIN_PROFIT',
            'SOURCING_ROI_MULTIPLE',
            'SOURCING_SHIP_COST',
        ],
        'Autopilot': [
            'OFFERS_ENABLED',
            'OFFER_DISCOUNT_PCT',
            'OFFER_MIN_WATCHERS',
            'MARKDOWN_ENABLED',
            'MARKDOWN_AFTER_DAYS',
            'MARKDOWN_STEP_PCT',
            'MARKDOWN_FLOOR_PCT',
            'OFFERS_MARKDOWNS_DRY_RUN',
            'DISCOVERY_MARKDOWN_AFTER_DAYS',
            'DISCOVERY_MARKDOWN_STEP_PCT',
            'DISCOVERY_MARKDOWN_FLOOR_PCT',
            'AUTOPILOT_RUN_HOUR',
            'RELIST_ENABLED',
            'RELIST_MAX_TIMES',
        ],
        'Security': [
            'API_ACCESS_TOKEN',
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
        'API_ACCESS_TOKEN',
    ]
    
    def __init__(self, env_path: Optional[Path] = None):
        """
        Initialize the settings manager
        
        Args:
            env_path: Path to .env file. Defaults to finding .env in project root.
        """
        self._settings = {}
        self._comments = []  # Preserve comments from original file
        self._save_lock = threading.Lock()  # Guards read-modify-write of .env

        # Determine .env path
        if env_path:
            self.env_path = Path(env_path)
        else:
            # Walk up from this file's directory to filesystem root.
            # This supports git worktrees nested several levels deep.
            current = Path(__file__).resolve().parent
            found = False
            while True:
                candidate = current / ".env"
                if candidate.exists():
                    self.env_path = candidate
                    found = True
                    break
                parent = current.parent
                if parent == current:
                    break  # Reached filesystem root
                current = parent

            # Also check cwd as a fallback
            if not found:
                cwd_env = Path.cwd().resolve() / ".env"
                if cwd_env.exists():
                    self.env_path = cwd_env
                    found = True

            # Fallback if none found (will create new one in CWD)
            if not found:
                self.env_path = Path.cwd() / ".env"

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
        with self._save_lock:
            self._save_locked(settings)

    def _save_locked(self, settings: Optional[dict] = None) -> None:
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
        
        # Atomic write: .env holds all credentials — a crash mid-write must
        # never leave it truncated. Write a temp file, then swap in place.
        tmp_path = self.env_path.parent / (self.env_path.name + '.tmp')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.env_path)
    
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
_instance_lock = threading.Lock()


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance (thread-safe)"""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SettingsManager()
    return _instance


if __name__ == "__main__":
    # Test the settings manager
    logger.info("Testing Settings Manager...")
    
    manager = SettingsManager()
    settings = manager.load()
    
    logger.info(f"\nLoaded {len(settings)} settings from {manager.env_path}")
    logger.info("\nSettings by category:")
    
    for category, keys in SettingsManager.SETTING_CATEGORIES.items():
        logger.info(f"\n{category}:")
        for key in keys:
            value = manager.get(key, "(not set)")
            if manager.is_sensitive(key) and value != "(not set)":
                # Mask sensitive values
                value = value[:10] + "..." if len(value) > 10 else "***"
            logger.info(f"  {key}: {value}")
    
    # Validate
    errors = manager.validate()
    if errors:
        logger.warning("\n[WARN] Validation errors:")
        for error in errors:
            logger.warning(f"  - {error}")
    else:
        logger.info("\n[OK] All settings valid")
