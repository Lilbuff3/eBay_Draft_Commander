import re

from flask import Flask
from flask_socketio import SocketIO
from backend.config import Config
import logging

# Origins allowed to open the Socket.IO event bus: localhost (any port, for
# Vite dev on 5175), private LAN ranges (phone on home Wi-Fi), Tailscale CGNAT
# range and *.ts.net HTTPS hostnames. The LAN IP is DHCP-assigned, so this is
# a pattern rather than a fixed list.
_ALLOWED_ORIGIN_RE = re.compile(
    r'^https?://('
    r'localhost|127\.0\.0\.1'
    r'|192\.168\.\d{1,3}\.\d{1,3}'
    r'|10\.\d{1,3}\.\d{1,3}\.\d{1,3}'
    r'|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}'
    r'|100\.\d{1,3}\.\d{1,3}\.\d{1,3}'
    r'|[\w-]+\.[\w-]+\.ts\.net'
    r')(:\d+)?$'
)

def _is_allowed_origin(origin):
    return bool(origin and _ALLOWED_ORIGIN_RE.match(origin))

# async_mode='threading': the queue worker runs in a native threading.Thread and
# emits socket events directly from it. Under eventlet (without monkey_patch) that
# cross-thread emit is unsupported — events get dropped and the UI silently
# freezes. Threading mode makes native-thread emits first-class and removes the
# greenlet-starvation stalls caused by heavy native work (rembg/onnx, Pillow).
# ping_timeout=60 gives batch processing headroom before a false disconnect.
socketio = SocketIO(
    cors_allowed_origins=_is_allowed_origin,
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
)

def create_app(config_class=Config, queue_manager=None):
    """
    Application Factory for eBay Draft Commander Backend
    """
    app = Flask(__name__,
                template_folder=str(config_class.TEMPLATE_FOLDER),
                static_folder=str(config_class.STATIC_FOLDER))
    
    app.config.from_object(config_class)
    
    # Initialize Socket.IO with app
    socketio.init_app(app)
    
    # Configure Logging
    from backend.app.core.logger import configure_module_loggers, get_logger
    configure_module_loggers(use_json=False)
    
    # Log Data Directory
    from backend.app.core.paths import get_data_dir
    startup_logger = get_logger('startup')
    startup_logger.info(f"Data Directory: {get_data_dir()}")
    
    # Inject Dependencies
    if queue_manager:
        app.queue_manager = queue_manager
        # Link socketio to queue manager for event emitting
        queue_manager.socketio = socketio
        # Emit job_added event when new jobs are created (uploads, inbox scans)
        queue_manager.on_job_added = lambda job: socketio.emit('job_added', job.to_dict())
        # Give QueueManager access to app for context pushing in threads
        queue_manager.set_app(app)
    
    # Register Blueprints
    from backend.app.blueprints.ui import ui_bp
    app.register_blueprint(ui_bp)
    
    from backend.app.blueprints.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app
