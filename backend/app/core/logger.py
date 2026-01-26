"""
Centralized logging configuration for eBay Draft Commander.

Provides structured logging with:
- JSON format for production (machine-readable)
- Pretty console format for development (human-readable)
- Automatic log rotation (10MB per file, keeps 5 files)
- Request ID tracking for API call correlation
- Per-module log levels
"""
import logging
import logging.handlers
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import traceback


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for production environments"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'module': record.name,
            'message': record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'url'):
            log_data['url'] = record.url
        if hasattr(record, 'status_code'):
            log_data['status_code'] = record.status_code
            
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
            
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Format logs with colors for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',      # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format: 2026-01-19 14:30:15 [INFO] module_name: Message
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        message = f"{timestamp} {color}[{record.levelname}]{reset} {record.name}: {record.getMessage()}"
        
        # Add exception traceback if present
        if record.exc_info:
            message += '\n' + ''.join(traceback.format_exception(*record.exc_info))
            
        return message


def get_logger(
    name: str,
    level: str = 'INFO',
    log_to_file: bool = True,
    log_to_console: bool = True,
    use_json: bool = False
) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (usually module name)
        level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        log_to_file: Whether to write logs to file
        log_to_console: Whether to write logs to console
        use_json: Use JSON format (production) vs pretty format (development)
        
    Returns:
        Configured logger instance
        
    Example:
        logger = get_logger(__name__)
        logger.info("Server started", extra={'port': 5000})
        logger.error("API request failed", extra={'url': url, 'status_code': 500})
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(
            JSONFormatter() if use_json else ColoredFormatter()
        )
        logger.addHandler(console_handler)
    
    # File handler with rotation
    if log_to_file:
        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f'{name}.log'
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            JSONFormatter() if use_json else ColoredFormatter()
        )
        logger.addHandler(file_handler)
    
    return logger


def configure_module_loggers(use_json: bool = False):
    """
    Configure log levels for all application modules.
    
    Call this once at application startup to set appropriate
    log levels for different modules.
    
    Args:
        use_json: Whether to use JSON format (for production)
    """
    module_levels = {
        'web_server': 'INFO',      # API requests
        'queue_manager': 'DEBUG',  # Detailed queue state
        'ebay_api': 'INFO',        # eBay API calls
        'ebay_policies': 'INFO',   # Policy lookups
        'ai_analyzer': 'INFO',     # AI analysis results
        'create_from_folder': 'INFO',
        'photo_editor': 'INFO',
    }
    
    for module, level in module_levels.items():
        get_logger(module, level=level, use_json=use_json)


# Module-level convenience function
def log_exception(logger: logging.Logger, message: str, exc: Exception, extra: Optional[dict] = None):
    """
    Log an exception with full context.
    
    Args:
        logger: Logger instance
        message: Human-readable error message
        exc: Exception object
        extra: Additional context fields
    """
    log_data = extra or {}
    log_data['exception_type'] = type(exc).__name__
    logger.exception(message, extra=log_data)


if __name__ == '__main__':
    # Test the logger
    print("Testing logger module...\n")
    
    # Development format (pretty, colored)
    logger = get_logger('test', use_json=False)
    logger.debug("Debug message")
    logger.info("Info message", extra={'user': 'adam', 'action': 'login'})
    logger.warning("Warning message")
    logger.error("Error message", extra={'error_code': 500})
    
    try:
        raise ValueError("Test exception")
    except Exception as e:
        logger.exception("Caught an exception")
    
    print("\n" + "="*60 + "\n")
    
    # Production format (JSON)
    logger_json = get_logger('test_json', use_json=True, log_to_console=True, log_to_file=False)
    logger_json.info("Production log message", extra={'request_id': 'abc123'})
    
    print("\n✅ Logger module working correctly!")
