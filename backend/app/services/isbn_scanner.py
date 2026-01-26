
import os
import json
from pathlib import Path
from typing import Optional, List
try:
    from google import genai
    from google.genai import types
    from PIL import Image
except ImportError:
    print("⚠️ google-genai or PIL not installed")

class ISBNScanner:
    """
    Extracts ISBNs from images using Gemini Vision.
    """
    
    def __init__(self):
        env_path = Path(__file__).resolve().parents[3] / ".env"
        api_key = None
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('GOOGLE_API_KEY='):
                        api_key = line.split('=')[1].strip()
                        break
        
        if not api_key:
            api_key = os.getenv('GOOGLE_API_KEY')
            
        if api_key:
            self.client = genai.Client(api_key=api_key)
            print("✅ ISBN Scanner initialized (Gemini Vision)")
        else:
            self.client = None
            print("⚠️ ISBN Scanner disabled (No API Key)")

    def scan_image(self, image_path: str) -> Optional[str]:
        """
        Scan an image for an ISBN barcode.
        """
        if not self.client:
            return None
            
        try:
            # Load image
            img = Image.open(image_path)
            
            prompt = """Look at this image. Find the ISBN-13 or ISBN-10 barcode number. 
            Return ONLY the digits of the ISBN. No text, no formatting. 
            If no ISBN is visible, return 'None'."""
            
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[prompt, img]
            )
            
            text = response.text.strip()
            
            # Basic validation
            digits = ''.join(filter(str.isdigit, text))
            
            if len(digits) in [10, 13]:
                return digits
                
            return None
            
        except Exception as e:
            print(f"❌ ISBN Scan failed: {e}")
            return None

if __name__ == "__main__":
    # Test needs a real image path
    print("ISBN Scanner Service Ready")
