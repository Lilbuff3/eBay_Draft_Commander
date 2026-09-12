"""
Path resolution utilities for eBay Draft Commander.

Provides consistent path resolution for project directories
(data, logs) relative to the project root.
"""
from pathlib import Path


def get_app_directory() -> Path:
    """Project root (navigates up from backend/app/core/paths.py)."""
    return Path(__file__).parent.parent.parent.parent


def get_logs_dir() -> Path:
    """Logs directory at backend/app/core/logs (created if missing)."""
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_data_dir() -> Path:
    """Data directory at <project_root>/data for the database and state files."""
    data_dir = get_app_directory() / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
