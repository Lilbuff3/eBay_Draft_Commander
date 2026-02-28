from flask import Blueprint, jsonify
import time
import threading
import sys
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

@system_bp.route('/restart', methods=['POST'])
def restart_server():
    """Soft reboot the backend server"""
    def reboot():
        logger.info("Soft reboot triggered. Restarting process...")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=reboot).start()
    return jsonify({'success': True, 'message': 'Rebooting server...'}), 200
