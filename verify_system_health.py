import sys
import os
from pathlib import Path
import importlib.util

def check_file(path_str):
    if Path(path_str).exists():
        print(f"[OK] File found: {path_str}")
        return True
    print(f"[FAIL] Missing file: {path_str}")
    return False

def check_module(module_name):
    if importlib.util.find_spec(module_name):
        print(f"[OK] Module installed: {module_name}")
        return True
    print(f"[FAIL] Module missing: {module_name}")
    return False

def verify_settings():
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from backend.app.core.settings_manager import get_settings_manager
        settings = get_settings_manager()
        
        if settings.get('EBAY_APP_ID') and settings.get('GOOGLE_API_KEY'):
            print(f"[OK] Settings loaded successfully (Env: {settings.get('EBAY_ENVIRONMENT')})")
            return True
        else:
            print("[FAIL] Settings loaded but missing keys!")
            return False
    except Exception as e:
        print(f"[FAIL] Settings crashed: {e}")
        return False

def main():
    print("Running Draft Commander Health Check...")
    print("-" * 40)
    
    passes = 0
    checks = 0
    
    # 1. Check Critical Files
    critical_files = [
        'draft_commander.py',
        'web_server.py',
        '.env',
        'frontend/package.json',
        'static/app/index.html'
    ]
    
    for f in critical_files:
        checks += 1
        if check_file(f): passes += 1
        
    # 2. Check Python Modules
    modules = ['flask', 'PIL', 'requests', 'dotenv']
    for m in modules:
        checks += 1
        if check_module(m): passes += 1
        
    # 3. Check Settings Logic
    checks += 1
    if verify_settings(): passes += 1
    
    print("-" * 40)
    print(f"Health Check: {passes}/{checks} passed.")
    
    if passes == checks:
        print("✅ SYSTEM READY")
        sys.exit(0)
    else:
        print("❌ SYSTEM ISSUES DETECTED")
        sys.exit(1)

if __name__ == "__main__":
    main()
