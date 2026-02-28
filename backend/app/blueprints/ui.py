from flask import Blueprint, send_from_directory, current_app, redirect
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
    # static_folder is defined in create_app from helper config
    app_dir = Path(current_app.static_folder) / 'app'
    
    # If path exists as a file, serve it
    if path and (app_dir / path).exists():
        return send_from_directory(app_dir, path)
    
    # Otherwise serve index.html (for SPA routing)
    return send_from_directory(app_dir, 'index.html')

@ui_bp.route('/sw.js')
def serve_service_worker():
    """Serve service worker from build output"""
    app_dir = Path(current_app.static_folder) / 'app'
    return send_from_directory(app_dir, 'sw.js', mimetype='application/javascript')

@ui_bp.route('/manifest.webmanifest')
def serve_manifest_alias():
    app_dir = Path(current_app.static_folder) / 'app'
    return send_from_directory(app_dir, 'manifest.webmanifest', mimetype='application/manifest+json')

@ui_bp.route('/manifest.json')
def serve_manifest():
    app_dir = Path(current_app.static_folder) / 'app'
    # Vite PWA might generate manifest.webmanifest or manifest.json depending on config
    # Creating a fallback
    if (app_dir / 'manifest.json').exists():
        return send_from_directory(app_dir, 'manifest.json', mimetype='application/json')
    return send_from_directory(app_dir, 'manifest.webmanifest', mimetype='application/manifest+json')

@ui_bp.route('/icons/<path:filename>')
def serve_icons(filename):
    app_dir = Path(current_app.static_folder) / 'app'
    return send_from_directory(app_dir / 'icons', filename)

@ui_bp.route('/offline.html')
def serve_offline():
    app_dir = Path(current_app.static_folder) / 'app'
    return send_from_directory(app_dir, 'offline.html')
