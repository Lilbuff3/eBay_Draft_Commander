from flask import Blueprint, send_from_directory, current_app, redirect, make_response
from pathlib import Path

ui_bp = Blueprint('ui', __name__)

@ui_bp.route('/')
def index():
    """Redirect root to React SPA"""
    return redirect('/app/')

@ui_bp.route('/app')
def app_root():
    """Redirect /app to /app/ to ensure relative assets work"""
    return redirect('/app/')

@ui_bp.route('/app/')
@ui_bp.route('/app/<path:path>')
def serve_vite_app(path=''):
    """Serve the Vite-built React app"""
    app_dir = Path(current_app.static_folder) / 'app'
    
    # If path exists as a file, serve it (with special MIME handling)
    if path and (app_dir / path).exists():
        # Serve manifest with correct MIME type
        if path.endswith('manifest.json') or path.endswith('.webmanifest'):
            return send_from_directory(app_dir, path, mimetype='application/manifest+json')
        return send_from_directory(app_dir, path)
    
    # Otherwise serve index.html (for SPA routing)
    return send_from_directory(app_dir, 'index.html')

# --- Service Worker ---
# VitePWA registers SW from /app/sw.js with scope /app/
# The SW file lives in static/app/sw.js after build
@ui_bp.route('/app/sw.js')
def serve_app_service_worker():
    """Serve service worker from /app/sw.js (where VitePWA registers it)"""
    app_dir = Path(current_app.static_folder) / 'app'
    response = make_response(
        send_from_directory(app_dir, 'sw.js', mimetype='application/javascript')
    )
    # Allow SW to control the entire site if needed
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@ui_bp.route('/sw.js')
def serve_service_worker():
    """Serve service worker from root (backward compatibility)"""
    app_dir = Path(current_app.static_folder) / 'app'
    response = make_response(
        send_from_directory(app_dir, 'sw.js', mimetype='application/javascript')
    )
    response.headers['Service-Worker-Allowed'] = '/'
    return response

# --- Manifest ---
@ui_bp.route('/manifest.webmanifest')
def serve_manifest_alias():
    app_dir = Path(current_app.static_folder) / 'app'
    return send_from_directory(app_dir, 'manifest.json', mimetype='application/manifest+json')

@ui_bp.route('/manifest.json')
def serve_manifest():
    app_dir = Path(current_app.static_folder) / 'app'
    return send_from_directory(app_dir, 'manifest.json', mimetype='application/manifest+json')

# --- Icons & Offline ---
@ui_bp.route('/icons/<path:filename>')
def serve_icons(filename):
    app_dir = Path(current_app.static_folder) / 'app'
    return send_from_directory(app_dir / 'icons', filename)

@ui_bp.route('/offline.html')
def serve_offline():
    app_dir = Path(current_app.static_folder) / 'app'
    return send_from_directory(app_dir, 'offline.html')

