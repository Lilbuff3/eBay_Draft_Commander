import os
from pathlib import Path

class Config:
    """Base Configuration"""
    # Project Root (backend/config.py -> backend -> root)
    BASE_DIR = Path(__file__).parent.parent
    
    # Paths
    TEMPLATE_FOLDER = BASE_DIR / 'templates'
    STATIC_FOLDER = BASE_DIR / 'static'
    DATA_DIR = BASE_DIR / 'data'
    FRONTEND_DIR = BASE_DIR / 'frontend' / 'dist'
    INBOX_DIR = BASE_DIR / 'inbox'
    
    # Settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    
    # Upload Limits (eBay 2026 Video Support: 150MB max + overhead)
    MAX_CONTENT_LENGTH = 160 * 1024 * 1024 # 160MB
    
    # Feature Flags
    AUTO_PUBLISH = os.environ.get('EBAY_AUTO_PUBLISH', 'false').lower() == 'true'
