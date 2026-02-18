import sys
import os
import logging
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

# Setup Boot Logging (Critical for Frozen App Debugging)
import builtins
def log_to_file(*args, **kwargs):
    try:
        log_path = Path("backend_boot.log")
        if getattr(sys, 'frozen', False):
            log_path = Path(sys.executable).parent / "backend_boot.log"
        
        # Construct message like print does
        msg = " ".join(map(str, args))
        
        with open(log_path, "a") as f:
            f.write(msg + "\n")
    except:
        pass

# Monkey patch print to log to file
builtins.print = log_to_file

# Redirect Stdout/Stderr to prevent crashes in frozen mode (where they are None)
if getattr(sys, 'frozen', False):
    try:
        log_dir = Path(sys.executable).parent
        sys.stdout = open(log_dir / 'backend_stdout.log', 'a')
        sys.stderr = open(log_dir / 'backend_stderr.log', 'a')
    except:
        pass # Best effort

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

from backend.app import create_app, socketio
from backend.app.services.queue_manager import QueueManager

def main():
    """Entry point for standalone execution (Electron/Headless)"""
    boot_logger.info("Starting eBay Draft Commander backend...")
    
    # Initialize Queue Manager
    try:
        boot_logger.info("Initializing QueueManager...")
        queue_manager = QueueManager()
        boot_logger.info("✅ QueueManager initialized successfully")
            
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
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
