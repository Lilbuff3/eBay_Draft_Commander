from flask import Flask
from flask_socketio import SocketIO
from backend.config import Config
import logging

# Primary Socket.IO instance — allow all origins in development
socketio = SocketIO(cors_allowed_origins="*")

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
    
    # Initialize MCP Client
    from backend.app.services.mcp_client import get_mcp_client
    # We don't connect immediately to avoid blocking startup if server is down,
    # but we ensure the singleton is ready.
    app.mcp_client = get_mcp_client()

    return app
