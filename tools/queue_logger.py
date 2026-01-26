"""
Queue Logger for eBay Draft Commander
Provides structured logging for queue operations with file and console output.
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional


class QueueLogger:
    """
    Structured logger for queue operations.
    
    Features:
    - Per-session log files
    - JSON-structured events
    - Console + file output
    - Color-coded console output
    """
    
    def __init__(self, base_path: Path = None, session_name: str = None):
        self.base_path = base_path or Path(__file__).parent
        self.logs_path = self.base_path / "logs"
        self.logs_path.mkdir(exist_ok=True)
        
        # Create session log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session_name = session_name or f"queue_{timestamp}"
        self.log_file = self.logs_path / f"{session_name}.log"
        self.json_file = self.logs_path / f"{session_name}.jsonl"
        
        # Setup Python logger
        self.logger = logging.getLogger(f"queue_{timestamp}")
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # File handler (detailed)
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)
        
        # Console handler (colored)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        self.info(f"📋 Log session started: {self.log_file.name}")
    
    def _log_json(self, level: str, event: str, data: dict = None):
        """Write structured JSON log entry"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "event": event,
            "data": data or {}
        }
        try:
            with open(self.json_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message)
        self._log_json("DEBUG", message, kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message)
        self._log_json("INFO", message, kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(f"⚠️ {message}")
        self._log_json("WARNING", message, kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(f"❌ {message}")
        self._log_json("ERROR", message, kwargs)
    
    def success(self, message: str, **kwargs):
        """Log success message (custom level)"""
        self.logger.info(f"✅ {message}")
        self._log_json("SUCCESS", message, kwargs)
    
    def job_start(self, job_id: str, folder_name: str):
        """Log job start event"""
        self.info(f"⚙️ Processing: {folder_name}", job_id=job_id, folder=folder_name)
    
    def job_complete(self, job_id: str, folder_name: str, listing_id: str = None, elapsed: float = None):
        """Log job completion"""
        msg = f"✅ Completed: {folder_name}"
        if listing_id:
            msg += f" → {listing_id}"
        if elapsed:
            msg += f" ({elapsed:.1f}s)"
        self.success(msg, job_id=job_id, listing_id=listing_id, elapsed=elapsed)
    
    def job_error(self, job_id: str, folder_name: str, error_type: str, error_message: str):
        """Log job error"""
        self.error(f"Failed: {folder_name} - {error_type}: {error_message}", 
                   job_id=job_id, error_type=error_type, error_message=error_message)
    
    def queue_start(self, total_jobs: int):
        """Log queue processing start"""
        self.info(f"🚀 Starting queue processing: {total_jobs} jobs")
    
    def queue_pause(self):
        """Log queue pause"""
        self.info("⏸️ Queue paused")
    
    def queue_resume(self):
        """Log queue resumed"""
        self.info("▶️ Queue resumed")
    
    def queue_complete(self, completed: int, failed: int, total: int, elapsed: float = None):
        """Log queue completion"""
        msg = f"🏁 Queue complete: {completed}/{total} succeeded, {failed} failed"
        if elapsed:
            msg += f" ({elapsed:.1f}s total)"
        self.info(msg)
    
    def get_log_path(self) -> Path:
        """Get path to current log file"""
        return self.log_file


# Global logger instance
_global_logger: Optional[QueueLogger] = None


def get_logger() -> QueueLogger:
    """Get or create global logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = QueueLogger()
    return _global_logger


def new_session(session_name: str = None) -> QueueLogger:
    """Start a new logging session"""
    global _global_logger
    _global_logger = QueueLogger(session_name=session_name)
    return _global_logger


# Test
if __name__ == "__main__":
    logger = new_session("test_session")
    
    logger.info("Test info message")
    logger.warning("Test warning message")
    logger.error("Test error message")
    logger.success("Test success message")
    
    logger.job_start("ABC123", "test_item")
    logger.job_complete("ABC123", "test_item", "123456789", 5.2)
    logger.job_error("DEF456", "broken_item", "ImageUploadError", "No images found")
    
    logger.queue_complete(5, 1, 6, 45.3)
    
    print(f"\n📁 Log file: {logger.get_log_path()}")
