import google.generativeai as genai
import os
from pathlib import Path

def test_gemini():
    env_path = Path('.env')
    api_key = None
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip().startswith('GOOGLE_API_KEY='):
                    api_key = line.split('=')[1].strip()
                    break
    
    if not api_key:
        api_key = os.getenv('GOOGLE_API_KEY')
        
    if not api_key:
        print("❌ GOOGLE_API_KEY not found")
        return

    try:
        genai.configure(api_key=api_key)
        # Check available models
        print("Checking available models...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"  - {m.name}")
        
        # Test 2.0 flash
        model_name = 'gemini-2.0-flash-exp'
        print(f"\nTesting {model_name}...")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Hello, respond with 'Success' if you can read this.")
        print(f"Response: {response.text}")
        print(f"✅ {model_name} is working!")
        
    except Exception as e:
        print(f"❌ Gemini test failed: {e}")

if __name__ == "__main__":
    test_gemini()
