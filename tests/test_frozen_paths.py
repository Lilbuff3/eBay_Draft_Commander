"""
Regression Test: Path Resolution in Frozen (PyInstaller) Environment

Tests that the application correctly resolves paths to writable locations
when running as a packaged executable, preventing write permission crashes.

This test simulates the PyInstaller frozen environment by mocking sys.frozen
and sys._MEIPASS attributes.
"""
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.core.paths import (
    is_frozen,
    get_app_directory,
    get_logs_dir,
    get_data_dir
)


def test_is_frozen_detection():
    """Test detection of PyInstaller frozen environment"""
    print("Test: Frozen Environment Detection...")
    
    # Test non-frozen (normal execution)
    assert not is_frozen(), "Should not be frozen in normal execution"
    print("  [PASS] Non-frozen detection works")
    
    # Test frozen (mocked PyInstaller environment)
    with patch.object(sys, 'frozen', True, create=True):
        with patch.object(sys, '_MEIPASS', '/tmp/_MEI12345', create=True):
            assert is_frozen(), "Should detect frozen environment"
            print("  [PASS] Frozen detection works")


def test_frozen_paths_are_writable():
    """Test that frozen environment uses writable directories"""
    print("\nTest: Frozen Paths Are Writable...")
    
    # Mock Windows frozen environment
    with patch.object(sys, 'frozen', True, create=True):
        with patch.object(sys, '_MEIPASS', 'C:\\Temp\\_MEI12345', create=True):
            with patch.object(sys, 'platform', 'win32'):
                # Mock LOCALAPPDATA environment variable
                with patch.dict(os.environ, {'LOCALAPPDATA': 'C:\\Users\\TestUser\\AppData\\Local'}):
                    app_dir = get_app_directory()
                    logs_dir = get_logs_dir()
                    data_dir = get_data_dir()
                    
                    # Verify paths are NOT in the temporary _MEI directory
                    assert '_MEI' not in str(app_dir), f"App dir should not be in _MEI: {app_dir}"
                    assert '_MEI' not in str(logs_dir), f"Logs dir should not be in _MEI: {logs_dir}"
                    assert '_MEI' not in str(data_dir), f"Data dir should not be in _MEI: {data_dir}"
                    
                    # Verify paths are in LOCALAPPDATA (user-writable)
                    assert 'AppData\\Local\\eBayDraftCommander' in str(app_dir), \
                        f"App dir should be in LOCALAPPDATA: {app_dir}"
                    assert 'AppData\\Local\\eBayDraftCommander\\logs' in str(logs_dir), \
                        f"Logs dir should be under app dir: {logs_dir}"
                    assert 'AppData\\Local\\eBayDraftCommander\\data' in str(data_dir), \
                        f"Data dir should be under app dir: {data_dir}"
                    
                    print(f"  [PASS] App Directory: {app_dir}")
                    print(f"  [PASS] Logs Directory: {logs_dir}")
                    print(f"  [PASS] Data Directory: {data_dir}")


def test_development_paths_use_project_root():
    """Test that development mode uses project-relative paths"""
    print("\nTest: Development Paths Use Project Root...")
    
    # Ensure we're in non-frozen mode
    if hasattr(sys, 'frozen'):
        delattr(sys, 'frozen')
    if hasattr(sys, '_MEIPASS'):
        delattr(sys, '_MEIPASS')
    
    app_dir = get_app_directory()
    logs_dir = get_logs_dir()
    data_dir = get_data_dir()
    
    # In development, app_dir should be project root
    assert app_dir.exists(), f"App directory should exist: {app_dir}"
    
    # Logs should be in backend/app/core/logs for development convenience
    assert 'backend' in str(logs_dir) or logs_dir.name == 'logs', \
        f"Logs dir should be in backend/app/core/logs: {logs_dir}"
    
    # Data should be in project root/data
    assert data_dir.name == 'data', f"Data dir should be named 'data': {data_dir}"
    
    print(f"  [PASS] App Directory: {app_dir}")
    print(f"  [PASS] Logs Directory: {logs_dir}")
    print(f"  [PASS] Data Directory: {data_dir}")


def test_logger_in_frozen_environment():
    """Test that logger works in frozen environment without crashing"""
    print("\nTest: Logger in Frozen Environment...")
    
    with patch.object(sys, 'frozen', True, create=True):
        with patch.object(sys, '_MEIPASS', 'C:\\Temp\\_MEI12345', create=True):
            with patch.object(sys, 'platform', 'win32'):
                with patch.dict(os.environ, {'LOCALAPPDATA': tempfile.gettempdir()}):
                    try:
                        from backend.app.core.logger import get_logger
                        
                        # This should NOT crash - it should create logs in temp dir
                        logger = get_logger('test_frozen', log_to_file=True)
                        logger.info("Test message in frozen environment")
                        
                        # Verify log file was created in writable location
                        logs_dir = get_logs_dir()
                        log_file = logs_dir / 'test_frozen.log'
                        
                        assert logs_dir.exists(), f"Logs directory should exist: {logs_dir}"
                        assert '_MEI' not in str(logs_dir), \
                            f"Logs should not be in _MEI directory: {logs_dir}"
                        
                        print(f"  [PASS] Logger created successfully")
                        print(f"  [PASS] Log directory: {logs_dir}")
                        
                    except Exception as e:
                        raise AssertionError(f"Logger should not crash in frozen env: {e}")


def test_queue_manager_in_frozen_environment():
    """Test that QueueManager works in frozen environment"""
    print("\nTest: QueueManager in Frozen Environment...")
    
    with patch.object(sys, 'frozen', True, create=True):
        with patch.object(sys, '_MEIPASS', 'C:\\Temp\\_MEI12345', create=True):
            with patch.object(sys, 'platform', 'win32'):
                with patch.dict(os.environ, {'LOCALAPPDATA': tempfile.gettempdir()}):
                    try:
                        from backend.app.services.queue_manager import QueueManager
                        
                        # This should NOT crash
                        qm = QueueManager()
                        
                        # Verify database is in writable location
                        assert qm.db_path.exists() or qm.db_path.parent.exists(), \
                            f"DB path should be writable: {qm.db_path}"
                        assert '_MEI' not in str(qm.db_path), \
                            f"DB should not be in _MEI directory: {qm.db_path}"
                        
                        print(f"  [PASS] QueueManager created successfully")
                        print(f"  [PASS] Database path: {qm.db_path}")
                        
                    except Exception as e:
                        raise AssertionError(f"QueueManager should not crash in frozen env: {e}")


def run_all_tests():
    """Run all frozen path tests"""
    print("=" * 70)
    print("REGRESSION TEST: Frozen Environment Path Resolution")
    print("=" * 70)
    
    test_is_frozen_detection()
    test_frozen_paths_are_writable()
    test_development_paths_use_project_root()
    test_logger_in_frozen_environment()
    test_queue_manager_in_frozen_environment()
    
    print("\n" + "=" * 70)
    print("[SUCCESS] ALL TESTS PASSED")
    print("=" * 70)


if __name__ == '__main__':
    run_all_tests()
