"""
Path resolution utilities for eBay Draft Commander.

Provides consistent path resolution for project directories
(data, logs, inbox, etc.) relative to the project root.
"""
from pathlib import Path


def get_app_directory() -> Path:
    """
    Get the project root directory.

    Returns:
        Path to project root directory
        (navigates up from backend/app/core/paths.py)
    """
    return Path(__file__).parent.parent.parent.parent


def get_logs_dir() -> Path:
    """
    Get the logs directory.

    Returns:
        Path to logs directory (created if it doesn't exist),
        located at <project_root>/backend/app/core/logs
    """
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_data_dir() -> Path:
    """
    Get the data directory for database and state files.

    Returns:
        Path to data directory (created if it doesn't exist),
        located at <project_root>/data
    """
    data_dir = get_app_directory() / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_inbox_dir() -> Path:
    """
    Get the inbox directory for raw listing data.

    Returns:
        Path to inbox directory (created if it doesn't exist),
        located at <project_root>/inbox
    """
    inbox_dir = get_app_directory() / 'inbox'
    inbox_dir.mkdir(parents=True, exist_ok=True)
    return inbox_dir


def get_ready_dir() -> Path:
    """
    Get the ready directory for processed listing data.

    Returns:
        Path to ready directory (created if it doesn't exist),
        located at <project_root>/ready
    """
    ready_dir = get_app_directory() / 'ready'
    ready_dir.mkdir(parents=True, exist_ok=True)
    return ready_dir


if __name__ == '__main__':
    print("Path Resolution Test")
    print("=" * 60)
    print(f"App Directory: {get_app_directory()}")
    print(f"Logs Directory: {get_logs_dir()}")
    print(f"Data Directory: {get_data_dir()}")
    print(f"Inbox Directory: {get_inbox_dir()}")
    print(f"Ready Directory: {get_ready_dir()}")
    print("=" * 60)
