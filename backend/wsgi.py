import sys
import os
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from backend.app import create_app
from backend.app.services.queue_manager import QueueManager

def main():
    """Entry point for standalone execution (Electron/Headless)"""
    # Initialize Queue Manager
    # Note: data_path defaults to 'data' in CWD or passed arg.
    # We assume CWD is project root when running this.
    try:
        queue_manager = QueueManager()
        
        # Initialize Processor
        # We need to wire up the processor just like web_server.py did
        try:
            from create_from_folder import create_listing_structured
            queue_manager.set_processor(create_listing_structured)
            print("✅ Structured Listing Processor wired to Queue Manager")
        except ImportError as e:
            print(f"❌ Failed to import processor: {e}")
            
    except Exception as e:
        print(f"❌ Failed to initialize QueueManager: {e}")
        queue_manager = None

    # Create App
    app = create_app(queue_manager=queue_manager)
    
    # Run Server
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting Backend Server on port {port}")
    
    # Debug=True is fine for dev, but we might want to toggle it
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
