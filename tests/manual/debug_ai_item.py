import sys
import os
from pathlib import Path
import json

# Add backend to path
sys.path.append(os.getcwd())

from backend.app.services.ai_analyzer import AIAnalyzer

def debug_analyze_item():
    print("Starting direct analyze_item debug...")
    analyzer = AIAnalyzer()
    
    test_folder = Path('inbox/web_upload_1772001574_d4d1')
    images = [str(p) for p in test_folder.glob('*.jpg')]
    
    print(f"Found {len(images)} images: {images}")
    
    if not images:
        print("No images found!")
        return

    print("Calling analyze_item...")
    try:
        result = analyzer.analyze_item(images)
        print("\n=== SUCCESSFUL CALL ===")
        print(f"Result Type: {type(result)}")
        print(f"Result Keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        if 'error' in result:
             print(f"Error in result: {result['error']}")
    except Exception as e:
        print("\n=== CRASHED ===")
        print(f"Exception Type: {type(e)}")
        print(f"Exception Message: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_analyze_item()
