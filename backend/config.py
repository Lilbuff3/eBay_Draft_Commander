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
    
    # Settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
