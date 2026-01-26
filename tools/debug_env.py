import sys
import os
from pathlib import Path

# Add project root to sys.path explicitly to mimic draft_commander behavior
sys.path.insert(0, str(Path(__file__).parent))

try:
    from backend.app.core.settings_manager import SettingsManager
    print(f"Successfully imported SettingsManager from backend.app.core")
except ImportError:
    try:
        from settings_manager import SettingsManager
        print(f"Successfully imported SettingsManager from root (or path)")
    except ImportError as e:
        print(f"Failed to import SettingsManager: {e}")
        sys.exit(1)

import inspect
print(f"SettingsManager file: {inspect.getfile(SettingsManager)}")

manager = SettingsManager()
print(f"Manager env_path: {manager.env_path}")
print(f"env_path exists: {manager.env_path.exists()}")

root_env = Path("c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/.env")
print(f"Root env exists: {root_env.exists()}")

settings = manager.get_all()
print(f"Loaded settings count: {len(settings)}")
if 'EBAY_APP_ID' in settings:
    print(f"EBAY_APP_ID: {settings['EBAY_APP_ID'][:5]}...")
else:
    print("EBAY_APP_ID not found in loaded settings")

print("\nSys.path:")
for p in sys.path:
    print(f"  {p}")
