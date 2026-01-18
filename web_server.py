"""
Web Control Server for eBay Draft Commander Pro
Provides a mobile-friendly web interface for remote monitoring and control
"""
import os
import io
import socket
import threading
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file

# Try to import qrcode for QR generation
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


class WebControlServer:
    """Web server for remote control of Draft Commander"""
    
    def __init__(self, queue_manager, port=5000):
        """
        Initialize the web server
        
        Args:
            queue_manager: Reference to the QueueManager instance
            port: Port to run the server on (default 5000)
        """
        self.queue_manager = queue_manager
        self.port = port
        self.host = '0.0.0.0'  # Bind to all interfaces
        self._thread = None
        self._running = False
        
        # Create Flask app
        template_dir = Path(__file__).parent / 'templates'
        static_dir = Path(__file__).parent / 'static'
        
        self.app = Flask(__name__, 
                        template_folder=str(template_dir),
                        static_folder=str(static_dir))
        
        # Disable Flask's default logging in production
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        # Register routes
        self._register_routes()
        
    def _register_routes(self):
        """Register all Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main mobile dashboard"""
            return render_template('mobile.html')
        
        @self.app.route('/api/status')
        def get_status():
            """Get current queue status"""
            stats = self.queue_manager.get_stats()
            
            # Determine overall status
            if self.queue_manager.is_paused():
                status = 'paused'
            elif self.queue_manager.is_processing():
                status = 'processing'
            elif stats['pending'] > 0:
                status = 'ready'
            else:
                status = 'idle'
            
            # Get current job if processing
            current_job = None
            for job in self.queue_manager.jobs:
                if job.status.value == 'processing':
                    current_job = {
                        'name': job.folder_name,
                        'started': job.started_at.isoformat() if job.started_at else None
                    }
                    break
            
            return jsonify({
                'status': status,
                'stats': stats,
                'current_job': current_job,
                'progress': {
                    'current': stats['completed'] + stats['failed'],
                    'total': stats['total'],
                    'percent': int((stats['completed'] + stats['failed']) / max(stats['total'], 1) * 100)
                }
            })
        
        @self.app.route('/api/jobs')
        def get_jobs():
            """Get all jobs with details"""
            jobs = []
            for job in self.queue_manager.jobs:
                jobs.append({
                    'id': job.id,
                    'name': job.folder_name,
                    'status': job.status.value,
                    'listing_id': job.listing_id,
                    'offer_id': job.offer_id,
                    'price': job.result.get('price') if job.result else None,
                    'error_type': job.error_type,
                    'error_message': job.error_message,
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                })
            return jsonify(jobs)
        
        @self.app.route('/api/stats')
        def get_stats():
            """Get queue statistics"""
            return jsonify(self.queue_manager.get_stats())
        
        @self.app.route('/api/start', methods=['POST'])
        def start_queue():
            """Start queue processing"""
            try:
                self.queue_manager.start_processing()
                return jsonify({'success': True, 'message': 'Queue started'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/pause', methods=['POST'])
        def pause_queue():
            """Pause queue processing"""
            try:
                self.queue_manager.pause()
                return jsonify({'success': True, 'message': 'Queue paused'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/resume', methods=['POST'])
        def resume_queue():
            """Resume queue processing"""
            try:
                self.queue_manager.resume()
                return jsonify({'success': True, 'message': 'Queue resumed'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/retry', methods=['POST'])
        def retry_failed():
            """Retry all failed jobs"""
            try:
                count = len(self.queue_manager.get_failed_jobs())
                self.queue_manager.retry_failed()
                return jsonify({'success': True, 'retried': count})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/clear', methods=['POST'])
        def clear_completed():
            """Clear completed jobs"""
            try:
                self.queue_manager.clear_completed()
                return jsonify({'success': True, 'message': 'Cleared completed jobs'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/qr')
        def get_qr_code():
            """Generate QR code for the web URL"""
            if not HAS_QRCODE:
                return "QR code library not installed", 404
            
            url = self.get_url()
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save to bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            return send_file(img_bytes, mimetype='image/png')
    
    def get_local_ip(self):
        """Get the local IP address"""
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def get_url(self):
        """Get the full URL for accessing the web interface"""
        ip = self.get_local_ip()
        return f"http://{ip}:{self.port}"
    
    def start(self):
        """Start the web server in a background thread"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        
        print(f"📱 Web Control started at {self.get_url()}")
    
    def _run_server(self):
        """Run the Flask server (called in background thread)"""
        try:
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        except Exception as e:
            print(f"Web server error: {e}")
            self._running = False
    
    def stop(self):
        """Stop the web server"""
        self._running = False
        # Flask doesn't have a clean shutdown in threads, but daemon=True
        # means it will stop when the main app exits
    
    def is_running(self):
        """Check if server is running"""
        return self._running


# Test the server standalone
if __name__ == "__main__":
    # Create a mock queue manager for testing
    class MockQueueManager:
        def __init__(self):
            self.jobs = []
            self._paused = False
            self._processing = False
        
        def get_stats(self):
            return {'pending': 3, 'completed': 5, 'failed': 1, 'total': 9}
        
        def is_paused(self):
            return self._paused
        
        def is_processing(self):
            return self._processing
        
        def start_processing(self):
            self._processing = True
            print("Queue started")
        
        def pause(self):
            self._paused = True
            print("Queue paused")
        
        def resume(self):
            self._paused = False
            print("Queue resumed")
        
        def retry_failed(self):
            print("Retrying failed")
        
        def get_failed_jobs(self):
            return []
        
        def clear_completed(self):
            print("Cleared completed")
    
    mock = MockQueueManager()
    server = WebControlServer(mock)
    
    print(f"Starting test server at {server.get_url()}")
    print("Press Ctrl+C to stop")
    
    # Run in main thread for testing
    server.app.run(host='0.0.0.0', port=5000, debug=True)
