"""
Path resolution utilities for eBay Draft Commander.

Handles different execution contexts:
- Development: Running from source code
- Production: Running as PyInstaller packaged executable

Key Features:
- Detects PyInstaller frozen environment
- Uses user-writable directories for logs and data in production
- Maintains project-relative paths during development
- Cross-platform support (Windows, macOS, Linux)
"""
import sys
import os
from pathlib import Path


def is_frozen() -> bool:
    """
    Check if running as PyInstaller bundle.
    
    Returns:
        True if running as packaged executable, False if running from source
    """
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_app_directory() -> Path:
    """
    Get the appropriate base directory based on execution context.
    
    Returns:
        Path to application directory:
        - Development: Project root directory
        - Production: User-writable app data directory
        
    Platform-specific production paths:
        - Windows: %LOCALAPPDATA%\\eBayDraftCommander
        - macOS: ~/Library/Application Support/eBayDraftCommander
        - Linux: ~/.ebay-draft-commander
    """
    if is_frozen():
        # Running as packaged app - use user-writable location
        if sys.platform == 'win32':
            # Windows: Use LOCALAPPDATA
            base_dir = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'eBayDraftCommander'
        elif sys.platform == 'darwin':
            # macOS: Use Application Support
            base_dir = Path.home() / 'Library' / 'Application Support' / 'eBayDraftCommander'
        else:
            # Linux/Unix: Use hidden directory in home
            base_dir = Path.home() / '.ebay-draft-commander'
        
        # Ensure directory exists
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir
    else:
        # Running from source - use project root
        # Navigate up from: backend/app/core/paths.py -> project root
        return Path(__file__).parent.parent.parent.parent


def get_logs_dir() -> Path:
    """
    Get the logs directory.
    
    Returns:
        Path to logs directory (created if it doesn't exist)
        - Development: <project_root>/backend/app/core/logs
        - Production: <app_directory>/logs
    """
    if is_frozen():
        log_dir = get_app_directory() / 'logs'
    else:
        # Development: Keep logs next to logger.py for convenience
        log_dir = Path(__file__).parent / 'logs'
    
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_data_dir() -> Path:
    """
    Get the data directory for database and state files.
    
    Returns:
        Path to data directory (created if it doesn't exist)
        - Development: <project_root>/data
        - Production: <app_directory>/data
    """
    data_dir = get_app_directory() / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_inbox_dir() -> Path:
    """
    Get the inbox directory for raw listing data.
    
    Returns:
        Path to inbox directory (created if it doesn't exist)
    """
    inbox_dir = get_app_directory() / 'inbox'
    inbox_dir.mkdir(parents=True, exist_ok=True)
    return inbox_dir


def get_ready_dir() -> Path:
    """
    Get the ready directory for processed listing data.
    
    Returns:
        Path to ready directory (created if it doesn't exist)
    """
    ready_dir = get_app_directory() / 'ready'
    ready_dir.mkdir(parents=True, exist_ok=True)
    return ready_dir


if __name__ == '__main__':
    # Test path resolution
    print("Path Resolution Test")
    print("=" * 60)
    print(f"Is Frozen: {is_frozen()}")
    print(f"App Directory: {get_app_directory()}")
    print(f"Logs Directory: {get_logs_dir()}")
    print(f"Data Directory: {get_data_dir()}")
    print(f"Inbox Directory: {get_inbox_dir()}")
    print(f"Ready Directory: {get_ready_dir()}")
    print("=" * 60)
    
    if is_frozen():
        print("✅ Running as packaged app - using user-writable directories")
    else:
        print("✅ Running from source - using project directories")
