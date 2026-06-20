import os
from pathlib import Path

def load_dotenv_manually(base_path):
    """Manually load .env file into os.environ.

    Searches for .env starting at base_path and walking up every parent
    directory until found or root is reached.  Also checks cwd() as a
    final fallback.  This ensures git worktrees (which can be nested
    several levels deep) still find the project-root .env.
    """
    candidates = []

    # Walk up from base_path to filesystem root
    current = base_path.resolve()
    while True:
        candidates.append(current / '.env')
        parent = current.parent
        if parent == current:
            break  # Reached filesystem root
        current = parent

    # Also check cwd as a fallback (may differ from base_path)
    cwd_env = Path.cwd().resolve() / '.env'
    if cwd_env not in candidates:
        candidates.append(cwd_env)

    for env_path in candidates:
        try:
            if env_path.exists():
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            # Don't overwrite existing env vars
                            if key.strip() not in os.environ:
                                os.environ[key.strip()] = value.strip()
                return True
        except Exception:
            pass  # Fail silently in config loader to prevent startup crashes
    return False

class Config:
    """Base Configuration"""
    
    # __file__ is backend/config.py -> parent=backend -> parent=root
    BASE_DIR = Path(__file__).parent.parent
    load_dotenv_manually(BASE_DIR)

    # Paths
    TEMPLATE_FOLDER = BASE_DIR / 'templates'
    STATIC_FOLDER = BASE_DIR / 'static'
    DATA_DIR = BASE_DIR / 'data'
    INBOX_DIR = Path(os.environ.get('INBOX_PATH', BASE_DIR / 'inbox'))

    # Hermes WhatsApp capture intake — sibling directory next to inbox/
    CAPTURES_DIR = INBOX_DIR.parent / 'captures'
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

    FRONTEND_DIR = BASE_DIR / 'frontend' / 'dist'
    
    # feature flags and limits...
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    MAX_CONTENT_LENGTH = 160 * 1024 * 1024 
    AUTO_PUBLISH = os.environ.get('AUTO_PUBLISH', 'false').lower() == 'true'
    CONFIDENCE_THRESHOLD = int(os.environ.get('CONFIDENCE_THRESHOLD', 85))
    AUTO_PUBLISH_MIN_PRICE = float(os.environ.get('AUTO_PUBLISH_MIN_PRICE', 15.00))

    # eBay Configuration
    EBAY_APP_ID = os.environ.get('EBAY_APP_ID')
    EBAY_FULFILLMENT_POLICY = os.environ.get('EBAY_FULFILLMENT_POLICY')
    EBAY_PAYMENT_POLICY = os.environ.get('EBAY_PAYMENT_POLICY')
    EBAY_RETURN_POLICY = os.environ.get('EBAY_RETURN_POLICY')
    EBAY_MERCHANT_LOCATION = os.environ.get('EBAY_MERCHANT_LOCATION')
    EBAY_POSTAL_CODE = os.environ.get('EBAY_POSTAL_CODE')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
