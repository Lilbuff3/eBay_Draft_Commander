import sys
import os
import logging
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

# Early boot logger - writes to file before main logging system is ready
def setup_boot_logger():
    """Create a basic logger for early application startup"""
    try:
        from backend.app.core.paths import get_logs_dir
        log_file = get_logs_dir() / 'backend_boot.log'
        
        boot_logger = logging.getLogger('boot')
        boot_logger.setLevel(logging.DEBUG)
        
        # File handler only (no console - console may not exist in packaged app)
        handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        boot_logger.addHandler(handler)
        
        return boot_logger
    except Exception as e:
        # If even boot logger fails, we're in serious trouble
        # But don't crash - return a null logger
        null_logger = logging.getLogger('boot_fallback')
        null_logger.addHandler(logging.NullHandler())
        return null_logger

boot_logger = setup_boot_logger()

from backend.app import create_app
from backend.app.services.queue_manager import QueueManager

def main():
    """Entry point for standalone execution (Electron/Headless)"""
    boot_logger.info("Starting eBay Draft Commander backend...")
    
    # Initialize Queue Manager
    try:
        boot_logger.info("Initializing QueueManager...")
        queue_manager = QueueManager()
        boot_logger.info("✅ QueueManager initialized successfully")
        
        # Initialize Processor
        try:
            from create_from_folder import create_listing_structured
            queue_manager.set_processor(create_listing_structured)
            boot_logger.info("✅ Structured Listing Processor wired to Queue Manager")
        except ImportError as e:
            boot_logger.error(f"❌ Failed to import processor: {e}")
            
    except Exception as e:
        boot_logger.error(f"❌ Failed to initialize QueueManager: {e}", exc_info=True)
        queue_manager = None

    # Create App
    boot_logger.info("Creating Flask application...")
    app = create_app(queue_manager=queue_manager)
    
    # Run Server
    port = int(os.environ.get('PORT', 5000))
    boot_logger.info(f"🚀 Starting Backend Server on port {port}")
    
    # Debug=True is fine for dev, but we might want to toggle it
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
