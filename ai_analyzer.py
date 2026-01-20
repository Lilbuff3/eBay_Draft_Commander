"""
AI Image Analyzer for eBay Draft Commander
Uses Gemini to analyze product photos and extract listing data
"""
import os
import base64
import json
from pathlib import Path
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

class AIAnalyzer:
    """Analyzes product images using Gemini AI"""
    
    def __init__(self):
        """Initialize the Gemini client"""
        env_path = Path(__file__).parent / ".env"
        api_key = None
        
        # Load API key custom
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('GOOGLE_API_KEY='):
                        api_key = line.split('=')[1].strip()
                        break
        
        if not api_key:
            # Fallback for dev/testing or system env
            api_key = os.getenv('GOOGLE_API_KEY')
            
        if not api_key:
            print("⚠️ GOOGLE_API_KEY not found in .env")
            self.model = None
            return

        genai.configure(api_key=api_key)
        
        # Use the latest Gemini 3 Flash model
        self.model = genai.GenerativeModel('gemini-3-flash-preview') 
        # Fallback to 2.0 or 1.5 if 3.0 not available:
        # self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        # self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        print("✅ AI Analyzer initialized (Google AI Studio)")


    
    def encode_image(self, image_path):
        """Encode image to base64"""
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"⚠️ Could not encode {image_path}: {e}")
            return None
    
    def get_images_from_folder(self, folder_path, max_images=8):
        """Get all images from a folder"""
        folder = Path(folder_path)
        extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        
        images = []
        for ext in extensions:
            images.extend(folder.glob(f'*{ext}'))
            images.extend(folder.glob(f'*{ext.upper()}'))
        
        # Sort by name and limit
        images = sorted(set(images))[:max_images]
        return [str(img) for img in images]
    
    def analyze_item(self, image_paths):
        """
        Analyze images and extract structured listing data
        
        Args:
            image_paths: List of paths to item images
            
        Returns:
            Dict with all extracted listing data
        """
        if not image_paths:
            return {"error": "No images provided"}
        
        # Encode all images
        encoded_images = []
        for path in image_paths:
            encoded = self.encode_image(path)
            if encoded:
                encoded_images.append(encoded)
        
        if not encoded_images:
            return {"error": "Could not encode any images"}
        
        # Build the prompt
        prompt = """Analyze these product photos for a high-end eBay listing.
        
ROLE: You are an expert e-commerce copywriter. Your goal is to write a persuasive, professional, and SEO-optimized listing that converts views into sales.

OUTPUT FORMAT: Return a JSON object with this EXACT structure:
{
    "identification": {
        "brand": "exact brand name from label",
        "model": "exact model number",
        "mpn": "manufacturer part number if visible",
        "serial_number": "if visible, otherwise null",
        "product_type": "specific item type"
    },
    "condition": {
        "state": "New|New - Open Box|Used - Like New|Used - Good|Used - Acceptable|For Parts",
        "wear_level": "none|minimal|light|moderate|heavy",
        "accessories_visible": ["list", "any", "accessories"],
        "notes": "brief condition summary used for condition description field"
    },
    "specifications": {
        "color": "main color",
        "dimensions": "if determinable",
        "other_specs": {"key": "value"}
    },
    "origin": {
        "country_of_manufacture": "if visible",
        "certifications": ["UL", "CE", "etc"]
    },
    "listing": {
        "suggested_title": "Optimized 80-char Title: Brand Model Keywords (No filler words)",
        "description": "HTML_STRING",
        "suggested_price": "XX.XX",
        "price_reasoning": "brief logic"
    },
    "category_keywords": ["keyword1", "keyword2"]
}

INSTRUCTIONS FOR 'description' FIELD (HTML_STRING):
1. Use valid HTML tags: <h2>, <ul>, <li>, <b>, <br>, <p>.
2. Do NOT use <html>, <head>, or <body> tags.
3. Structure the description exactly like this:
   <h2>Product Overview</h2>
   <p>[Persuasive summary of the item: what it is, why it's great, and accurate identification]</p>
   
   <h2>Condition</h2>
   <p><b>[State]</b>: [Detailed observation of wear, scratches, or lack thereof. Be honest but professional.]</p>
   
   <h2>Key Features</h2>
   <ul>
     <li>[Feature 1]</li>
     <li>[Feature 2]</li>
     <li>...</li>
   </ul>
   
   <h2>Included in Sale</h2>
   <ul>
     <li>[Item itself]</li>
     <li>[Accessory 1 (if visible)]</li>
     <li>[Power cord (if visible)]</li>
     <li>...</li>
   </ul>
   
   <h2>Shipping & Handling</h2>
   <p>We ship within 24 hours of payment (Mon-Fri) from a US-based warehouse. Your item will be professionally packed to ensure safe arrival. Buy with confidence!</p>

4. TONE: Professional, confident, and "Top Rated Seller" quality.
5. ACCURACY: Do not hallucinate accessories not shown in photos."""

        # Safety settings to avoid blocking product descriptions
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "max_output_tokens": 4000,
            "response_mime_type": "application/json",
        }
        
        # Prepare content parts
        parts = [prompt]
        
        for img_b64 in encoded_images:
            parts.append({
                "mime_type": "image/jpeg",
                "data": base64.b64decode(img_b64)
            })
            
        try:
            if not self.model:
                 return {"error": "AI Model not initialized (Check API Key)"}

            response = self.model.generate_content(
                parts,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Parse the JSON response
            response_text = response.text
            
            # Clean up the response if needed
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            data = json.loads(response_text.strip())
            
            if isinstance(data, list):
                if data:
                    data = data[0]
                else:
                    return {"error": "AI returned an empty list"}
            
            data['image_paths'] = image_paths
            data['image_count'] = len(image_paths)
            
            return data
            
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse AI response as JSON: {e}")
            print(f"   Raw response: {response_text[:500]}...")
            return {"error": f"JSON parse error: {e}", "raw": response_text}
            
        except Exception as e:
            print(f"❌ AI analysis failed: {e}")
            return {"error": str(e)}
    
    def analyze_folder(self, folder_path):
        """Analyze all images in a folder"""
        images = self.get_images_from_folder(folder_path)
        
        if not images:
            return {"error": f"No images found in {folder_path}"}
        
        print(f"📸 Analyzing {len(images)} images from {Path(folder_path).name}...")
        
        # Run analysis
        result = self.analyze_item(images)
        
        # Check for errors in result
        if result.get('error'):
            return result
            
        # Save result to ai_data.json
        try:
            data_path = Path(folder_path) / 'ai_data.json'
            with open(data_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"✅ Saved analysis to {data_path.name}")
        except Exception as e:
            print(f"⚠️ Failed to save ai_data.json: {e}")
            # We still return success as we have the data in memory/result
            
        # Return success structure for queue manager
        return {
            'success': True,
            'data': result,
            'listing_id': None, # No listing created yet, just analysis
            'offer_id': None
        }


# Test the analyzer
if __name__ == "__main__":
    print("Testing AI Analyzer...")
    
    analyzer = AIAnalyzer()
    
    # Test with sample images if available
    inbox = Path(__file__).parent / "inbox"
    
    if inbox.exists():
        folders = [f for f in inbox.iterdir() if f.is_dir()]
        
        if folders:
            print(f"\nFound {len(folders)} item folders in inbox")
            
            # Analyze first folder
            result = analyzer.analyze_folder(folders[0])
            print(json.dumps(result, indent=2))
        else:
            print("\nNo item folders found in inbox/")
            print("Create a folder and add photos to test")
    else:
        print(f"\nInbox folder not found: {inbox}")
