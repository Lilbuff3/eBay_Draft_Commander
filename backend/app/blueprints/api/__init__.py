import hmac
import os

from flask import Blueprint, jsonify, request
from .system_api import system_bp
from .queue_api import queue_bp
from .jobs_api import jobs_bp
from .listings_api import listings_bp
from .lookup_api import lookup_bp
from .analytics_api import analytics_bp
from .settings_api import settings_bp
from .migration_api import migration_bp

api_bp = Blueprint('api', __name__)

# Register sub-blueprints with empty prefix to maintain original /api/... compatibility
# as paths are fully defined in the sub-blueprints.
api_bp.register_blueprint(system_bp, url_prefix='/system')
api_bp.register_blueprint(queue_bp, url_prefix='')
api_bp.register_blueprint(jobs_bp, url_prefix='')
api_bp.register_blueprint(listings_bp, url_prefix='')
api_bp.register_blueprint(lookup_bp, url_prefix='')
api_bp.register_blueprint(analytics_bp, url_prefix='')
api_bp.register_blueprint(settings_bp, url_prefix='/settings')
api_bp.register_blueprint(migration_bp, url_prefix='')

# Loopback callers (desktop browser, Hermes bridge, supervisor health poll) are
# trusted; remote callers (LAN/Tailscale) must present X-API-Key matching
# API_ACCESS_TOKEN from .env. Set the token via the Settings page on the
# server machine. If no token is configured, remote access is denied.
_LOOPBACK_ADDRS = ('127.0.0.1', '::1')


def _is_key_exempt() -> bool:
    """Endpoints that must work without a header: <img> tags can't send one."""
    if request.path == '/api/system/health':
        return True
    return (request.method == 'GET'
            and request.path.startswith('/api/job/')
            and '/image/' in request.path)


@api_bp.before_request
def require_api_key():
    if request.remote_addr in _LOOPBACK_ADDRS:
        return None
    if _is_key_exempt():
        return None
    # Read live from SettingsManager so a token saved via the Settings page
    # takes effect without a restart; fall back to the boot-time environment.
    from backend.app.core.settings_manager import get_settings_manager
    expected = get_settings_manager().get('API_ACCESS_TOKEN') or os.environ.get('API_ACCESS_TOKEN', '')
    provided = request.headers.get('X-API-Key', '')
    if expected and provided and hmac.compare_digest(expected, provided):
        return None
    message = ('Missing or invalid X-API-Key'
               if expected else
               'Remote access requires API_ACCESS_TOKEN to be set in Settings on the server machine')
    return jsonify({'error': 'Unauthorized', 'message': message}), 401


@api_bp.errorhandler(Exception)
def handle_api_error(error):
    """Catch unhandled exceptions and return structured JSON instead of HTML 500."""
    from flask import current_app
    from backend.app.core.logger import get_logger
    logger = get_logger(__name__)
    logger.exception(f"Unhandled API error: {error}")
    message = str(error) if current_app.debug else 'An unexpected error occurred'
    return jsonify({'error': 'Internal server error', 'message': message}), 500


@api_bp.errorhandler(404)
def handle_not_found(error):
    return jsonify({'error': 'Not found'}), 404
