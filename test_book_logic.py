
import sys
import traceback
from pathlib import Path
from backend.app.services.ai_analyzer import AIAnalyzer

def test_book_scan():
    print("📚 Testing Book Scan Logic...")
    
    analyzer = AIAnalyzer()
    
    # Use the generated test artifact
    image_path = r"C:\Users\adam\.gemini\antigravity\brain\76b06f0d-8944-4557-94b5-b96ae5c6d2d4\test_book_cover_1769195196493.png"
    
    if not Path(image_path).exists():
        print(f"❌ Test image not found: {image_path}")
        return
        
    print(f"📸 Analyzing: {Path(image_path).name}")
    
    try:
        # 1. Force identification phase to detect "Book"
        # We simulate the first phase returning "product_type": "Book" 
        # normally the AI detects this, but for this unit test of the LOGIC, 
        # we want to ensure the ISBN scanner triggers.
        # Actually, let's multiple-step it. analyze_item calls analyze_with_research logic?
        # modify identify to return "Book"? 
        # No, let's trust prompt engineering or just call identify first.
        
        # Testing full flow with research enabled
        result = analyzer.analyze_with_research([image_path])
        
        # The prompt in analyze_item detects product type.
        # If it says "Book", the new logic should fire.
        
        print("\n--- Result ---")
        if 'error' in result:
             print(f"Error: {result['error']}")
        else:
             print(f"Title: {result.get('listing', {}).get('suggested_title')}")
             print(f"Mode: {result.get('analysis_mode')}")
             print(f"ISBN: {result.get('identification', {}).get('mpn')}")
             
             if result.get('analysis_mode') == 'book_scan':
                 print("✅ SUCCESS: Book Mode Triggered!")
             else:
                 print("❌ FAILED: Book Mode NOT Triggered.")
                 print(f"Product Type detected: {result.get('identification', {}).get('product_type')}")
                 
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    test_book_scan()
