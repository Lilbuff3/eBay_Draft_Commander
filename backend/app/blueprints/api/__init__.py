from flask import Blueprint, jsonify
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
