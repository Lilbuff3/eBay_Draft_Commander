from flask import Blueprint, jsonify, request
from backend.app.core.settings_manager import get_settings_manager
from backend.app.core.logger import get_logger

settings_bp = Blueprint('settings', __name__)
logger = get_logger('api.settings')

@settings_bp.route('', methods=['GET'])
def get_app_settings():
    """Get all application settings from .env (sensitive values masked)"""
    settings_manager = get_settings_manager()
    all_settings = settings_manager.get_all()
    for key in list(all_settings.keys()):
        if settings_manager.is_sensitive(key) and all_settings[key]:
            val = all_settings[key]
            all_settings[key] = '••••' + val[-4:] if len(val) > 4 else '••••'
    return jsonify(all_settings)

@settings_bp.route('', methods=['POST'])
def save_app_settings():
    """Save application settings to .env (only whitelisted keys)"""
    settings_manager = get_settings_manager()
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    # Build whitelist from SETTING_CATEGORIES and DEFAULTS
    allowed_keys = set()
    for keys in settings_manager.SETTING_CATEGORIES.values():
        allowed_keys.update(keys)
    allowed_keys.update(settings_manager.DEFAULTS.keys())

    filtered = {k: v for k, v in data.items() if k in allowed_keys}
    skipped = [k for k in data if k not in allowed_keys]
    if skipped:
        logger.warning(f"Settings save: rejected unknown keys: {skipped}")

    try:
        settings_manager.save(filtered)
        return jsonify({
            'success': True,
            'message': 'Settings saved successfully',
            'saved_count': len(filtered),
            'skipped': skipped
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
