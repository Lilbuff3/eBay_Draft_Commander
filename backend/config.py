import os
import sys
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
    
    # Determine Root Path
    if getattr(sys, 'frozen', False):
        # PyInstaller: sys.executable is the .exe
        # We want data to be persistent, so let's use the folder containing the .exe
        _EXE_DIR = Path(sys.executable).parent
        BASE_DIR = _EXE_DIR
        
        # Load Env Vars explicitly for Frozen app
        load_dotenv_manually(BASE_DIR)
        
    else:
        # Dev: __file__ is backend/config.py -> parent=backend -> parent=root
        BASE_DIR = Path(__file__).parent.parent
        # Load .env into os.environ for dev mode too
        load_dotenv_manually(BASE_DIR)

    # Paths
    # In frozen mode, PyInstaller extracts resources to _MEI temporary folder
    # BUT we want persistent data to stay with the executable (or AppData)
    # TEMPLATES/STATIC must rely on internal PyInstaller paths if bundled, 
    # but specific user data (DB/Inbox) should be external.
    
    if getattr(sys, 'frozen', False):
        # Internal Resources (Images/Templates) - bundled in exe
        _INTERNAL = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else BASE_DIR
        TEMPLATE_FOLDER = _INTERNAL / 'backend' / 'templates' # Adjusted for --add-data if needed, but we use API mostly
        STATIC_FOLDER = _INTERNAL / 'backend' / 'static'
        
        # External Data (DB, Inbox) - Next to .exe or custom path from env
        DATA_DIR = BASE_DIR / 'data'
        INBOX_DIR = Path(os.environ.get('INBOX_PATH', BASE_DIR / 'inbox'))
    else:
        TEMPLATE_FOLDER = BASE_DIR / 'templates'
        STATIC_FOLDER = BASE_DIR / 'static'
        DATA_DIR = BASE_DIR / 'data'
        # Allow custom inbox path via environment variable
        INBOX_DIR = Path(os.environ.get('INBOX_PATH', BASE_DIR / 'inbox'))

    FRONTEND_DIR = BASE_DIR / 'frontend' / 'dist'
    
    # feature flags and limits...
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    MAX_CONTENT_LENGTH = 160 * 1024 * 1024 
    AUTO_PUBLISH = os.environ.get('EBAY_AUTO_PUBLISH', 'false').lower() == 'true'
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
