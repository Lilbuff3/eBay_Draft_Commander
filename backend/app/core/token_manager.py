"""
Token Manager — Single source of truth for eBay API access tokens.

Architecture:
    .env              → static config (APP_ID, CERT_ID, REFRESH_TOKEN)
    SQLite app_tokens → rotating access token (2h TTL, atomic writes)
    In-memory cache   → hot path (no I/O per API call)

All modules call TokenManager.get_access_token() instead of reading tokens directly.
The manager handles refresh transparently — callers never think about expiry.
"""
import os
import time
import base64
import threading
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional
from backend.app.core.logger import get_logger
from backend.app.core.settings_manager import get_settings_manager

logger = get_logger('token_manager')

# eBay access tokens last 2 hours. Refresh 10 minutes before expiry to avoid edge cases.
TOKEN_TTL_SECONDS = 7200
REFRESH_BUFFER_SECONDS = 600  # refresh 10 min early

EBAY_TOKEN_URL_PROD = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_TOKEN_URL_SANDBOX = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"

EBAY_SCOPES = [
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
]


class TokenManager:
    """Thread-safe, DB-backed, memory-cached eBay token manager.
    
    Usage:
        from backend.app.core.token_manager import get_token_manager
        tm = get_token_manager()
        token = tm.get_access_token()  # always valid, auto-refreshes
    """
    
    def __init__(self):
        self._access_token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        self._lock = threading.Lock()
        self._db_initialized = False
        
        # Load any existing token from DB on startup
        self._load_from_db()
    
    # --- Public API ---
    
    def get_access_token(self) -> Optional[str]:
        """Get a valid eBay access token. Refreshes automatically if expired.
        
        Returns:
            The access token string, or None if no refresh token is configured.
        """
        # Fast path: cached and not expired
        if self._is_valid():
            return self._access_token
        
        # Slow path: need to refresh
        with self._lock:
            # Double-check after acquiring lock (another thread may have refreshed)
            if self._is_valid():
                return self._access_token
            
            if self._refresh():
                return self._access_token
            
            # Refresh failed — return whatever we have (may be expired but better than None)
            if self._access_token:
                logger.warning("Using potentially expired token — refresh failed")
                return self._access_token
            
            return None
    
    def store_tokens(self, access_token: str, refresh_token: Optional[str] = None, 
                     expires_in: int = TOKEN_TTL_SECONDS):
        """Store tokens after OAuth code exchange.
        
        - Access token → SQLite + memory (rotates often)
        - Refresh token → .env via SettingsManager (rarely rotates)
        """
        with self._lock:
            self._access_token = access_token
            self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            # Persist access token to DB
            self._save_to_db(access_token, self._expires_at)
            
            # Also set in os.environ for any code that reads it directly (legacy compat)
            os.environ['EBAY_USER_TOKEN'] = access_token
            
            # Persist refresh token to .env (only if provided/rotated)
            if refresh_token:
                settings = get_settings_manager()
                settings.set('EBAY_REFRESH_TOKEN', refresh_token)
                settings.save()
                os.environ['EBAY_REFRESH_TOKEN'] = refresh_token
                logger.info("Refresh token saved to .env")
            
            logger.info(f"Access token stored (expires {self._expires_at.strftime('%H:%M:%S UTC')})")
    
    def force_refresh(self) -> bool:
        """Manually trigger a token refresh. Returns True on success."""
        with self._lock:
            return self._refresh()
    
    def get_token_status(self) -> dict:
        """Get current token status for diagnostics / UI."""
        has_token = bool(self._access_token)
        is_expired = not self._is_valid()
        
        settings = get_settings_manager()
        has_refresh = bool(settings.get('EBAY_REFRESH_TOKEN'))
        has_app_id = bool(settings.get('EBAY_APP_ID'))
        has_cert_id = bool(settings.get('EBAY_CERT_ID'))
        
        return {
            'has_access_token': has_token,
            'is_expired': is_expired if has_token else None,
            'expires_at': self._expires_at.isoformat() if self._expires_at else None,
            'has_refresh_token': has_refresh,
            'has_credentials': has_app_id and has_cert_id,
        }
    
    # --- Private ---
    
    def _is_valid(self) -> bool:
        """Check if cached token exists and is not expired (with buffer)."""
        if not self._access_token or not self._expires_at:
            return False
        now = datetime.now(timezone.utc)
        # Make expires_at timezone-aware if it isn't
        exp = self._expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return now < (exp - timedelta(seconds=REFRESH_BUFFER_SECONDS))
    
    def _refresh(self) -> bool:
        """Exchange refresh token for a new access token. Must be called under lock."""
        settings = get_settings_manager()
        refresh_token = settings.get('EBAY_REFRESH_TOKEN')
        app_id = settings.get('EBAY_APP_ID')
        cert_id = settings.get('EBAY_CERT_ID')
        
        if not refresh_token:
            logger.info("No refresh token configured — set EBAY_REFRESH_TOKEN in Settings")
            return False
        
        if not app_id or not cert_id:
            logger.warning("Missing EBAY_APP_ID or EBAY_CERT_ID — configure in Settings")
            return False
        
        credentials = f"{app_id}:{cert_id}"
        encoded = base64.b64encode(credentials.encode()).decode()
        
        environment = settings.get('EBAY_ENVIRONMENT', 'production')
        token_url = EBAY_TOKEN_URL_SANDBOX if environment == 'sandbox' else EBAY_TOKEN_URL_PROD
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {encoded}'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'scope': ' '.join(EBAY_SCOPES)
        }
        
        try:
            response = requests.post(token_url, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data['access_token']
                expires_in = token_data.get('expires_in', TOKEN_TTL_SECONDS)
                
                self._access_token = access_token
                self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                # Persist to DB
                self._save_to_db(access_token, self._expires_at)
                
                # Update os.environ for legacy code
                os.environ['EBAY_USER_TOKEN'] = access_token
                
                # If eBay rotated the refresh token, save that too
                new_refresh = token_data.get('refresh_token')
                if new_refresh and new_refresh != refresh_token:
                    settings.set('EBAY_REFRESH_TOKEN', new_refresh)
                    settings.save()
                    os.environ['EBAY_REFRESH_TOKEN'] = new_refresh
                    logger.info("Refresh token rotated and saved to .env")
                
                logger.info(f"✅ Token refreshed (expires in {expires_in}s)")
                return True
            else:
                logger.error(f"❌ Refresh failed ({response.status_code}): {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Token refresh error: {e}")
            return False
    
    def _save_to_db(self, token: str, expires_at: datetime):
        """Atomically save access token to SQLite."""
        try:
            from backend.app.core.database import AppToken, init_db
            from backend.app.core.paths import get_data_dir
            
            db_path = get_data_dir() / "commander.db"
            SessionFactory = init_db(db_path)
            session = SessionFactory()
            
            try:
                existing = session.query(AppToken).filter_by(key='ebay_access_token').first()
                if existing:
                    existing.value = token
                    existing.expires_at = expires_at
                    existing.updated_at = datetime.utcnow()
                else:
                    session.add(AppToken(
                        key='ebay_access_token',
                        value=token,
                        expires_at=expires_at,
                        updated_at=datetime.utcnow()
                    ))
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to save token to DB: {e}")
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"DB access failed during token save: {e}")
    
    def _load_from_db(self):
        """Load cached token from SQLite on startup."""
        try:
            from backend.app.core.database import AppToken, init_db
            from backend.app.core.paths import get_data_dir
            
            db_path = get_data_dir() / "commander.db"
            if not db_path.exists():
                return
            
            SessionFactory = init_db(db_path)
            session = SessionFactory()
            
            try:
                row = session.query(AppToken).filter_by(key='ebay_access_token').first()
                if row:
                    self._access_token = row.value
                    self._expires_at = row.expires_at
                    if self._expires_at and self._expires_at.tzinfo is None:
                        self._expires_at = self._expires_at.replace(tzinfo=timezone.utc)
                    
                    # Set in os.environ for legacy compat
                    os.environ['EBAY_USER_TOKEN'] = row.value
                    
                    if self._is_valid():
                        logger.info(f"Loaded valid token from DB (expires {self._expires_at.strftime('%H:%M:%S UTC')})")
                    else:
                        logger.info("Loaded expired token from DB — will refresh on first use")
            finally:
                session.close()
                
        except Exception as e:
            logger.warning(f"Could not load token from DB: {e}")


# --- Singleton ---

_instance: Optional[TokenManager] = None
_instance_lock = threading.Lock()


def get_token_manager() -> TokenManager:
    """Get the global TokenManager singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = TokenManager()
    return _instance
