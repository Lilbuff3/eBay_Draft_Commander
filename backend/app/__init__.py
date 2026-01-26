from flask import Flask
from flask_socketio import SocketIO
from backend.config import Config

# Primary Socket.IO instance
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
    
    # Inject Dependencies
    if queue_manager:
        app.queue_manager = queue_manager
        # Link socketio to queue manager for event emitting
        queue_manager.socketio = socketio
        # Give QueueManager access to app for context pushing in threads
        queue_manager.set_app(app)
    
    # Register Blueprints
    from backend.app.blueprints.ui import ui_bp
    app.register_blueprint(ui_bp)
    
    from backend.app.blueprints.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app
