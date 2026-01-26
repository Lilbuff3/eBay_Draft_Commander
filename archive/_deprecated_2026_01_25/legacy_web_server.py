"""
Web Control Server Shim
Compatibility wrapper for the new Flask backend.
"""
import threading
import socket
from backend.app.core.logger import get_logger
from backend.app import create_app

class WebControlServer:
    """Wrapper for Flask app to maintain interface with draft_commander.py"""
    
    def __init__(self, queue_manager, port=5000):
        self.port = port
        self.host = '0.0.0.0'
        # Create the Flask app using the new factory
        self.app = create_app(queue_manager=queue_manager)
        
        from backend.app import socketio
        self.socketio = socketio
        
        self._thread = None
        self._running = False
        self.logger = get_logger('web_server')
        self.logger.info(f"Initializing web server shim on port {port}")

    def run_server(self):
        """Run Flask app with Socket.IO (blocking)"""
        try:
            # Use socketio.run instead of app.run for WebSocket support
            self.socketio.run(self.app, host=self.host, port=self.port, debug=False, use_reloader=False, log_output=True)
        except Exception as e:
            self.logger.error(f"Server crashed: {e}")
            self._running = False

    def start(self):
        """Start server in a background thread"""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self.run_server, daemon=True)
        self._thread.start()
        self.logger.info(f"Web server thread started")

    def stop(self):
        """Stop the web server"""
        self._running = False
        # Flask doesn't have a clean shutdown method for threaded usage without complex hacks
        # But since it's a daemon thread, it will exit when the main app exits.
        self.logger.info("Stopping web server (daemon thread will exit)")

    def is_running(self):
        return self._running

    def get_url(self):
        """Get local network URL"""
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return f"http://{local_ip}:{self.port}"
        except:
            return f"http://localhost:{self.port}"

if __name__ == "__main__":
    # Test standalone
    import sys
    import os
    from pathlib import Path
    base_path = Path(__file__).parent
    sys.path.insert(0, str(base_path))
    sys.path.insert(0, str(base_path / "tools"))
    
    from backend.app.services.queue_manager import QueueManager
    qm = QueueManager()
    server = WebControlServer(qm)
    server.start()
    
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
