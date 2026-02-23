from flask import Blueprint
from .system_api import system_bp
from .queue_api import queue_bp
from .jobs_api import jobs_bp
from .listings_api import listings_bp
from .lookup_api import lookup_bp
from .analytics_api import analytics_bp
from .settings_api import settings_bp

api_bp = Blueprint('api', __name__)

# Register sub-blueprints with empty prefix to maintain original /api/... compatibility
# as paths are fully defined in the sub-blueprints.
api_bp.register_blueprint(system_bp, url_prefix='')
api_bp.register_blueprint(queue_bp, url_prefix='')
api_bp.register_blueprint(jobs_bp, url_prefix='')
api_bp.register_blueprint(listings_bp, url_prefix='')
api_bp.register_blueprint(lookup_bp, url_prefix='')
api_bp.register_blueprint(analytics_bp, url_prefix='')
api_bp.register_blueprint(settings_bp, url_prefix='/settings')
