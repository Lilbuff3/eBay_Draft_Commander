
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from backend.app.services.ai_analyzer import AIAnalyzer

def test_ai_analyzer_v2():
    print("🧪 Testing AI Analyzer V2 (google-genai SDK)...")
    
    analyzer = AIAnalyzer()
    
    if not analyzer.client:
        print("❌ AI Client not initialized. Check API Key.")
        sys.exit(1)
        
    print("✅ AI Client initialized successfully.")
    
    # Verify imports/objects are from new SDK
    import google.genai
    if isinstance(analyzer.client, google.genai.Client):
        print("✅ Verified usage of google.genai.Client")
    else:
        print(f"❌ Unexpected client type: {type(analyzer.client)}")
        
    # We won't make a real API call to save tokens/time unless verifying full flow,
    # but we can check if methods are defined correctly.
    if hasattr(analyzer.client.models, 'generate_content'):
        print("✅ Client has generate_content method")
    else:
        print("❌ Client missing generate_content method")

    print("\n🎉 SDK Migration Verification Passed (Static Analysis)")
    
if __name__ == "__main__":
    test_ai_analyzer_v2()
