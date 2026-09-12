"""
Centralized logging configuration for eBay Draft Commander.

Provides:
- Pretty, colored console format
- Automatic log rotation (10MB per file, keeps 5 files)
- Per-module loggers
"""
import logging
import logging.handlers
import sys
from datetime import datetime
import traceback
from backend.app.core.paths import get_logs_dir


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
    log_to_console: bool = True
) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually module name)
        level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        log_to_file: Whether to write logs to file
        log_to_console: Whether to write logs to console

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Server started", extra={'port': 5000})
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
        console_handler.setFormatter(ColoredFormatter())
        logger.addHandler(console_handler)

    # File handler with rotation
    if log_to_file:
        log_file = get_logs_dir() / f'{name}.log'
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(ColoredFormatter())
        logger.addHandler(file_handler)

    return logger
