import sys
from pathlib import Path
import os

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.app.services.ai_analyzer import AIAnalyzer
from backend.app.services.ebay_service import eBayService
from dotenv import load_dotenv

def check_health():
    print("="*60)
    print(" eBay Draft Commander - Health Check (Phase 1)")
    print("="*60)
    
    # 1. Environment
    env_path = Path(__file__).parent.parent / ".env"
    print(f"\n[1] Configuration")
    if env_path.exists():
        load_dotenv(env_path)
        print(f" ✅ .env found at {env_path}")
        # Check keys presence (don't print them)
        google_key = os.getenv('GOOGLE_API_KEY')
        ebay_token = os.getenv('EBAY_USER_TOKEN')
        print(f"    GOOGLE_API_KEY: {'[PRESENT]' if google_key else '❌ MISSING'}")
        print(f"    EBAY_USER_TOKEN: {'[PRESENT]' if ebay_token else '❌ MISSING'}")
    else:
        print(f" ❌ .env NOT found at {env_path}")
    
    # 2. Gemini AI
    print(f"\n[2] Gemini AI Check")
    try:
        analyzer = AIAnalyzer()
        if not analyzer.client:
            print(" ❌ AI Client failed to initialize")
        else:
            # Simple generation test
            print("    Testing model 'gemini-3-flash-preview'...", end="", flush=True)
            try:
                # Use a lightweight generate call
                from google.genai import types
                resp = analyzer.client.models.generate_content(
                    model='gemini-3-flash-preview',
                    contents="Reply with 'OK'",
                    config=types.GenerateContentConfig(max_output_tokens=100) # Increased tokens
                )
                if hasattr(resp, 'text') and resp.text:
                    print(f" ✅ Success! Response: {resp.text.strip()}")
                else:
                    print(f" ⚠️ Response empty. Attributes: {dir(resp)}")
                    if hasattr(resp, 'candidates'):
                        print(f"    Candidates: {resp.candidates}")
            except Exception as e:
                print(f" ❌ Model Call Failed: {e}")
                
    except Exception as e:
        print(f" ❌ Critical AI Error: {e}")

    # 3. eBay API
    print(f"\n[3] eBay API Check")
    try:
        service = eBayService()
        status, code = service.check_connection_status()
        if status.get('status') == 'connected':
            print(f" ✅ Connection Valid: {status.get('message')}")
        else:
            print(f" ⚠️ Connection Issue: {status.get('message')} (Code: {code})")
            
        # Optional: Check Inventory
        try:
             inv, code = service.get_active_listings()
             count = inv.get('total', 0) if isinstance(inv, dict) else 0
             print(f"    Active Inventory Items: {count} (Inventory API Accessible)")
        except Exception as e:
             print(f"    ⚠️ Inventory Check Failed: {e}")

    except Exception as e:
        print(f" ❌ Critical eBay Error: {e}")

    print("\n" + "="*60)
    print(" Health Check Complete")
    print("="*60)

if __name__ == "__main__":
    check_health()
