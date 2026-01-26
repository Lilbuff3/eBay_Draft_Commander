from flask import Flask
from backend.config import Config

def create_app(config_class=Config, queue_manager=None):
    """
    Application Factory for eBay Draft Commander Backend
    """
    app = Flask(__name__,
                template_folder=str(config_class.TEMPLATE_FOLDER),
                static_folder=str(config_class.STATIC_FOLDER))
    
    app.config.from_object(config_class)
    
    # Inject Dependencies
    if queue_manager:
        app.queue_manager = queue_manager
    
    # Register Blueprints
    from backend.app.blueprints.ui import ui_bp
    app.register_blueprint(ui_bp)
    
    from backend.app.blueprints.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app
