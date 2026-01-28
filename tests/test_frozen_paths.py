"""
Test suite for frozen environment path resolution.

Verifies that the path resolution utilities correctly handle
PyInstaller packaged executables and avoid writing to read-only
temporary directories.
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile


class TestFrozenPaths(unittest.TestCase):
    """Test path resolution in frozen (PyInstaller) environments"""
    
    def setUp(self):
        """Reset any cached modules before each test"""
        if 'backend.app.core.paths' in sys.modules:
            del sys.modules['backend.app.core.paths']
    
    @patch('sys.frozen', True, create=True)
    @patch('sys._MEIPASS', '/tmp/_MEI12345', create=True)
    def test_is_frozen_detection(self):
        """Test that frozen environment is correctly detected"""
        from backend.app.core.paths import is_frozen
        self.assertTrue(is_frozen())
    
    def test_is_not_frozen_in_development(self):
        """Test that development environment is correctly detected"""
        from backend.app.core.paths import is_frozen
        self.assertFalse(is_frozen())
    
    @patch('sys.frozen', True, create=True)
    @patch('sys._MEIPASS', '/tmp/_MEI12345', create=True)
    @patch('sys.platform', 'win32')
    def test_windows_frozen_app_directory(self):
        """Test Windows frozen app uses LOCALAPPDATA"""
        from backend.app.core.paths import get_app_directory
        
        app_dir = get_app_directory()
        
        # Should use LOCALAPPDATA, not _MEIPASS
        self.assertNotIn('_MEI', str(app_dir))
        self.assertNotIn('Temp', str(app_dir))
        self.assertIn('eBayDraftCommander', str(app_dir))
        
        # Should be writable
        self.assertTrue(os.access(app_dir, os.W_OK))
    
    @patch('sys.frozen', True, create=True)
    @patch('sys._MEIPASS', '/tmp/_MEI12345', create=True)
    @patch('sys.platform', 'darwin')
    def test_macos_frozen_app_directory(self):
        """Test macOS frozen app uses Application Support"""
        from backend.app.core.paths import get_app_directory
        
        app_dir = get_app_directory()
        
        # Should use Application Support, not _MEIPASS
        self.assertNotIn('_MEI', str(app_dir))
        self.assertIn('eBayDraftCommander', str(app_dir))
        self.assertIn('Application Support', str(app_dir))
    
    @patch('sys.frozen', True, create=True)
    @patch('sys._MEIPASS', '/tmp/_MEI12345', create=True)
    @patch('sys.platform', 'linux')
    def test_linux_frozen_app_directory(self):
        """Test Linux frozen app uses home directory"""
        from backend.app.core.paths import get_app_directory
        
        app_dir = get_app_directory()
        
        # Should use home directory, not _MEIPASS
        self.assertNotIn('_MEI', str(app_dir))
        self.assertIn('.ebay-draft-commander', str(app_dir))
    
    def test_development_app_directory_uses_project_root(self):
        """Test development environment uses project root"""
        from backend.app.core.paths import get_app_directory
        
        app_dir = get_app_directory()
        
        # Should be project root (has backend/ directory)
        backend_dir = app_dir / 'backend'
        self.assertTrue(backend_dir.exists())
    
    @patch('sys.frozen', True, create=True)
    @patch('sys._MEIPASS', '/tmp/_MEI12345', create=True)
    def test_frozen_logs_directory_not_in_meipass(self):
        """Test that frozen app logs are NOT written to _MEIPASS"""
        from backend.app.core.paths import get_logs_dir
        
        log_dir = get_logs_dir()
        
        # Critical: Must NOT be in _MEIPASS (read-only)
        self.assertNotIn('_MEI', str(log_dir))
        self.assertNotIn('Temp\\_MEI', str(log_dir))
        
        # Should be writable
        self.assertTrue(os.access(log_dir, os.W_OK))
    
    @patch('sys.frozen', True, create=True)
    @patch('sys._MEIPASS', '/tmp/_MEI12345', create=True)
    def test_frozen_data_directory_not_in_meipass(self):
        """Test that frozen app data is NOT written to _MEIPASS"""
        from backend.app.core.paths import get_data_dir
        
        data_dir = get_data_dir()
        
        # Critical: Must NOT be in _MEIPASS (read-only)
        self.assertNotIn('_MEI', str(data_dir))
        self.assertNotIn('Temp\\_MEI', str(data_dir))
        
        # Should be writable
        self.assertTrue(os.access(data_dir, os.W_OK))
    
    def test_development_logs_directory_in_backend(self):
        """Test development logs are next to logger.py"""
        from backend.app.core.paths import get_logs_dir
        
        log_dir = get_logs_dir()
        
        # Should be backend/app/core/logs in development
        self.assertIn('backend', str(log_dir))
        self.assertIn('core', str(log_dir))
        self.assertIn('logs', str(log_dir))
    
    @patch('sys.frozen', True, create=True)
    @patch('sys._MEIPASS', '/tmp/_MEI12345', create=True)
    @patch('sys.platform', 'win32')
    def test_permission_fallback_to_temp(self):
        """Test fallback to temp directory when LOCALAPPDATA is not writable"""
        from backend.app.core.paths import get_app_directory
        
        with patch.dict(os.environ, {'LOCALAPPDATA': '/nonexistent/path'}):
            with patch('pathlib.Path.mkdir', side_effect=[PermissionError, None]):
                app_dir = get_app_directory()
                
                # Should fallback to temp directory
                self.assertIn(tempfile.gettempdir(), str(app_dir))
                self.assertIn('eBayDraftCommander', str(app_dir))
    
    @patch('sys.frozen', True, create=True)
    @patch('sys._MEIPASS', '/tmp/_MEI12345', create=True)
    def test_all_directories_writable_in_frozen(self):
        """Test that all directory functions return writable paths in frozen mode"""
        from backend.app.core.paths import (
            get_app_directory, get_logs_dir, get_data_dir,
            get_inbox_dir, get_ready_dir
        )
        
        directories = {
            'app': get_app_directory(),
            'logs': get_logs_dir(),
            'data': get_data_dir(),
            'inbox': get_inbox_dir(),
            'ready': get_ready_dir(),
        }
        
        for name, directory in directories.items():
            with self.subTest(directory=name):
                # Must NOT be in _MEIPASS
                self.assertNotIn('_MEI', str(directory), 
                    f"{name} directory is in read-only _MEIPASS")
                
                # Must be writable
                self.assertTrue(os.access(directory, os.W_OK),
                    f"{name} directory is not writable")
    
    @patch('sys.frozen', True, create=True)
    @patch('sys._MEIPASS', 'C:\\Users\\test\\AppData\\Local\\Temp\\_MEI250002', create=True)
    @patch('sys.platform', 'win32')
    def test_regression_original_error_fixed(self):
        """
        Regression test: Verify the original error is fixed.
        
        Original error:
        [WinError 3] The system cannot find the path specified: 
        'C:\\Users\\adam\\AppData\\Local\\Temp\\_MEI250002\\backend\\app\\core\\logs'
        """
        from backend.app.core.paths import get_logs_dir
        
        log_dir = get_logs_dir()
        
        # The bug was attempting to create logs inside _MEI directory
        # Verify this is now fixed
        self.assertNotIn('_MEI250002', str(log_dir))
        self.assertNotIn('_MEI', str(log_dir))
        
        # Verify we can actually create the directory (no WinError 3)
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            success = True
        except Exception as e:
            success = False
            error_msg = str(e)
        
        self.assertTrue(success, f"Failed to create log directory: {error_msg if not success else ''}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
