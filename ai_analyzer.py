"""
AI Image Analyzer for eBay Draft Commander
Uses Gemini to analyze product photos and extract listing data
"""
import os
import base64
import json
from pathlib import Path
from google import genai
from google.genai import types

class AIAnalyzer:
    """Analyzes product images using Gemini AI"""
    
    def __init__(self):
        """Initialize the Gemini client"""
        # Use Vertex AI with user's project (gen-lang-client has Gemini enabled)
        self.client = genai.Client(
            vertexai=True,
            project="gen-lang-client-0656287706",
            location="us-central1",
        )
        self.model = "gemini-2.5-flash"
        print("✅ AI Analyzer initialized (Vertex AI)")


    
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
        prompt = """Analyze these product photos for an eBay listing. Extract ALL visible information.

Return your analysis as a JSON object with this EXACT structure:
{
    "identification": {
        "brand": "exact brand name from label or your best identification",
        "model": "model number/name",
        "mpn": "manufacturer part number if visible",
        "serial_number": "if visible, otherwise null",
        "product_type": "what kind of item this is"
    },
    "condition": {
        "state": "New|New - Open Box|Used - Like New|Used - Good|Used - Acceptable|For Parts",
        "wear_level": "none|minimal|light|moderate|heavy",
        "packaging": "sealed|open box|no packaging",
        "accessories_visible": ["list", "any", "accessories"],
        "notes": "any condition notes"
    },
    "specifications": {
        "color": "main color",
        "material": "if determinable",
        "voltage": "if visible on label",
        "dimensions": "if determinable",
        "weight": "if determinable",
        "other_specs": {"key": "value pairs for any other visible specs"}
    },
    "origin": {
        "country_of_manufacture": "if visible (e.g., Made in Japan)",
        "certifications": ["UL", "CE", "etc if visible"]
    },
    "listing": {
        "suggested_title": "optimized 80-character eBay title",
        "description": "professional 2-3 paragraph description",
        "suggested_price": "XX.XX",
        "price_reasoning": "brief explanation of price suggestion"
    },
    "category_keywords": ["keywords", "to", "search", "for", "category"]
}

Be precise with brand names and part numbers - read them exactly from labels.
If something is not visible, use null or make an educated guess with a note.
The title MUST be 80 characters or less and include brand, model, and key features."""

        # Build the request
        prompt_part = types.Part.from_text(text=prompt)
        
        image_parts = []
        for img_b64 in encoded_images:
            # Determine mime type (assume JPEG for simplicity)
            image_parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(img_b64),
                    mime_type="image/jpeg",
                )
            )
        
        contents = [
            types.Content(
                role="user",
                parts=[prompt_part] + image_parts
            ),
        ]
        
        config = types.GenerateContentConfig(
            temperature=0.3,  # Lower temperature for more consistent extraction
            top_p=0.95,
            max_output_tokens=4000,
            response_mime_type="application/json",  # Request JSON response
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            
            # Parse the JSON response
            response_text = response.candidates[0].content.parts[0].text
            
            # Clean up the response if needed
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            data = json.loads(response_text.strip())
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
        
        return self.analyze_item(images)


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
