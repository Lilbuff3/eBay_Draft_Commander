# Bug Investigation: Write Permission Crash on Startup

## Bug Summary
The packaged backend executable (`web_server.exe`) crashes immediately on startup because it attempts to create a logs directory inside a read-only temporary directory created by PyInstaller.

**Error Message:**
```
[ERROR] Failed to initialize QueueManager: [WinError 3] The system cannot find the path specified: 
'C:\\Users\\adam\\AppData\\Local\\Temp\\_MEI250002\\backend\\app\\core\\logs'
```

## Root Cause Analysis

### Primary Issue: logger.py (lines 120-122)
The logger module attempts to create a logs directory relative to its own file location:

```python
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)
```

**Why this fails:**
- When packaged with PyInstaller, `Path(__file__)` resolves to the temporary extraction directory (e.g., `C:\Users\adam\AppData\Local\Temp\_MEI250002\backend\app\core\`)
- This temporary directory is **read-only** and controlled by PyInstaller
- Windows blocks the creation of new directories in this location
- The app crashes before any logging can occur

### Secondary Issue: queue_manager.py (line 76)
The QueueManager also uses `Path(__file__)` to determine the base path:

```python
self.base_path = base_path or Path(__file__).parent.parent.parent.parent
```

This would also fail in production, attempting to store data in the temporary read-only directory.

### Tertiary Issue: wsgi.py (multiple locations)
Contains multiple `print()` statements (lines 25, 27, 30, 38) that fail when no console window exists in the packaged application.

## Affected Components

1. **backend/app/core/logger.py**
   - `get_logger()` function (lines 120-122)
   - Hardcoded relative path for log directory

2. **backend/app/services/queue_manager.py**
   - `__init__()` method (line 76, 110)
   - Calls `get_logger()` during initialization (line 110)
   - Uses `Path(__file__)` for base_path determination (line 76)

3. **backend/wsgi.py**
   - Multiple `print()` statements
   - No console redirection for packaged environment

4. **backend/app/services/ebay/analytics.py, ebay_service.py, image_service.py, inventory.py, processor_service.py, scanner_service.py, trading.py**
   - All import and use `get_logger()`, potentially affected by the same issue

## Proposed Solution

### 1. Detect PyInstaller Environment
Add detection logic to determine if running as a packaged executable:

```python
import sys

def is_frozen():
    """Check if running as PyInstaller bundle"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
```

### 2. Use User-Writable Directories
When running as packaged app, use system-appropriate writable locations:

**For Logs:**
- Windows: `%LOCALAPPDATA%\eBayDraftCommander\logs`
- Example: `C:\Users\adam\AppData\Local\eBayDraftCommander\logs`

**For Data:**
- Use the same approach for database and data files
- Ensure the directory is created at startup

### 3. Implement Path Resolution Strategy

```python
def get_app_directory():
    """Get the appropriate directory based on execution context"""
    if is_frozen():
        # Running as packaged app - use LOCALAPPDATA
        if sys.platform == 'win32':
            base_dir = Path(os.environ['LOCALAPPDATA']) / 'eBayDraftCommander'
        else:
            # macOS/Linux fallback
            base_dir = Path.home() / '.ebay-draft-commander'
    else:
        # Running from source - use project root
        base_dir = Path(__file__).parent.parent.parent
    
    return base_dir
```

### 4. Update logger.py
- Replace hardcoded `Path(__file__).parent / 'logs'` with dynamic path resolution
- Create logs directory in user-writable location when frozen
- Fallback to project directory when running from source

### 5. Update queue_manager.py
- Replace `Path(__file__).parent.parent.parent.parent` with centralized path resolution
- Ensure data directory uses the same user-writable location

### 6. Update wsgi.py
- Replace `print()` statements with proper logging
- Add early boot logger that writes to file before main logger is initialized

## Edge Cases Considered

1. **Permissions**: User may not have write access to LOCALAPPDATA (rare but possible)
   - Solution: Catch permission errors and fallback to TEMP with unique app subfolder

2. **Multiple Instances**: Multiple app instances writing to same log directory
   - Solution: Current rotating file handler should handle this (already has locking)

3. **Migration**: Existing development logs shouldn't be lost
   - Solution: Development mode continues using project-relative paths

4. **Cross-Platform**: Solution should work on Windows, macOS, and Linux
   - Solution: Use platform detection for appropriate directories

## Implementation Steps

1. Create a new utility module: `backend/app/core/paths.py`
   - Implement `is_frozen()`, `get_app_directory()`, `get_logs_dir()`, `get_data_dir()`

2. Update `logger.py`:
   - Import path utilities
   - Replace hardcoded log_dir with `get_logs_dir()`

3. Update `queue_manager.py`:
   - Import path utilities
   - Replace base_path calculation with `get_app_directory()`

4. Update `wsgi.py`:
   - Create early boot logger that writes to file
   - Replace all `print()` with logger calls

5. Add regression test:
   - Test that simulates frozen environment
   - Verify paths resolve to writable locations
   - Ensure no attempt to write to `_MEIPASS`

## Implementation Summary

### Files Created
1. **backend/app/core/paths.py** (New)
   - Detects PyInstaller frozen environment using `sys.frozen` and `sys._MEIPASS`
   - Provides `get_app_directory()`, `get_logs_dir()`, `get_data_dir()` utilities
   - Returns user-writable directories in production (LOCALAPPDATA on Windows)
   - Returns project-relative paths in development

2. **tests/test_frozen_paths.py** (New)
   - Comprehensive regression tests for frozen environment path resolution
   - Mocks PyInstaller environment to verify correct behavior
   - Tests logger and QueueManager initialization in frozen mode

### Files Modified
1. **backend/app/core/logger.py**
   - Added import: `from backend.app.core.paths import get_logs_dir`
   - Replaced `Path(__file__).parent / 'logs'` with `get_logs_dir()`
   - Removed manual directory creation (handled by path utility)

2. **backend/app/services/queue_manager.py**
   - Added import: `from backend.app.core.paths import get_data_dir`
   - Replaced `Path(__file__).parent.parent.parent.parent` with `get_data_dir().parent`
   - Replaced manual data directory creation with `get_data_dir()`

3. **backend/wsgi.py**
   - Added early boot logger that writes to file before main logging system
   - Replaced all `print()` statements with `boot_logger` calls
   - Added exception handling with full traceback logging
   - Boot logger writes to `backend_boot.log` in logs directory

## Test Results

### Regression Test: test_frozen_paths.py
All tests **PASSED** ✓

**Test 1: Frozen Environment Detection**
- Non-frozen detection: PASS
- Frozen detection with mocked sys.frozen: PASS

**Test 2: Frozen Paths Are Writable**
- Verified paths NOT in _MEI directory: PASS
- Verified paths in LOCALAPPDATA/eBayDraftCommander: PASS
- Verified directories exist and are writable: PASS
- Example paths:
  - App: `C:\Users\...\AppData\Local\Temp\...\eBayDraftCommander`
  - Logs: `C:\Users\...\AppData\Local\Temp\...\eBayDraftCommander\logs`
  - Data: `C:\Users\...\AppData\Local\Temp\...\eBayDraftCommander\data`

**Test 3: Development Paths Use Project Root**
- App directory in project root: PASS
- Logs in backend/app/core/logs: PASS
- Data in project root/data: PASS

**Test 4: Logger in Frozen Environment**
- Logger initializes without crash: PASS
- Log files created in writable location: PASS
- No attempt to write to _MEI directory: PASS

**Test 5: QueueManager in Frozen Environment**
- QueueManager initializes without crash: PASS
- Database created in writable location: PASS
- No attempt to write to _MEI directory: PASS

### Verification
The implementation successfully fixes the write permission crash by:
1. Detecting when running as packaged executable
2. Using OS-appropriate user-writable directories
3. Creating all directories before attempting writes
4. Maintaining backward compatibility with development mode

The bug that caused `[WinError 3] The system cannot find the path specified` is now **RESOLVED**.
