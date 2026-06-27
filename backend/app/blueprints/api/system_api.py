from flask import Blueprint, jsonify
import time
import threading
import os
from backend.app.core.logger import get_logger

system_bp = Blueprint('system', __name__)
logger = get_logger('api.system')

@system_bp.route('/health', methods=['GET'])
def health_check():
    """Lightweight health check for monitoring / load balancers"""
    return jsonify({'status': 'ok', 'service': 'ebay-draft-commander'}), 200

@system_bp.route('/clear-taxonomy-cache', methods=['POST'])
def clear_taxonomy_cache():
    """Clear the taxonomy API response cache."""
    from backend.app.services.ebay.taxonomy import clear_taxonomy_cache as _clear
    _clear()
    return jsonify({'success': True, 'message': 'Taxonomy cache cleared'}), 200

# Exit code that tells the supervisor (run_service.py) to relaunch the child.
RESTART_EXIT_CODE = 42


@system_bp.route('/restart', methods=['POST'])
def restart_server():
    """Soft reboot the backend server.

    Requires the process to be launched under the supervisor (run_service.py),
    which sets DC_SUPERVISED=1. The handler exits with code 42; the supervisor
    sees it and relaunches the child into a freshly released port 5000.

    os.execv was unreliable on Windows: it does not release the eventlet
    listener socket before re-binding, leaving port 5000 unbound.
    """
    if not os.environ.get('DC_SUPERVISED'):
        return jsonify({
            'success': False,
            'error': 'Restart unavailable: backend is not running under the '
                     'supervisor. Launch via run_service.py to enable restart.',
        }), 409

    def reboot():
        logger.info(
            "Soft reboot triggered. Exiting with code %d for supervisor relaunch.",
            RESTART_EXIT_CODE,
        )
        time.sleep(1)  # let the HTTP response flush before the process dies
        os._exit(RESTART_EXIT_CODE)

    threading.Thread(target=reboot).start()
    return jsonify({'success': True, 'message': 'Rebooting server...'}), 200
