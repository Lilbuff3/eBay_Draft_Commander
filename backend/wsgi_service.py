"""
Background service launcher for eBay Draft Commander.
Wraps wsgi.py with proper stderr/stdout redirection to a log file
so the process can run headless via pythonw.exe or hidden cmd.exe.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Ensure data directory exists
DATA_DIR = ROOT_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Redirect stdout/stderr to log file BEFORE importing anything else
LOG_FILE = DATA_DIR / 'backend_service.log'
log_handle = open(LOG_FILE, 'a', encoding='utf-8', buffering=1)  # line-buffered
sys.stdout = log_handle
sys.stderr = log_handle

# Redirect stdin from devnull (required for pythonw.exe / hidden processes)
sys.stdin = open(os.devnull, 'r')

# Also redirect for any subprocesses
os.environ['PYTHONUNBUFFERED'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Now import and run the actual server
from backend.wsgi import main

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc(file=log_handle)
        log_handle.flush()
        raise
