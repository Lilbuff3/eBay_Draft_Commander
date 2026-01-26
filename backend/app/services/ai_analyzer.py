"""
AI Image Analyzer for eBay Draft Commander
Uses Gemini to analyze product photos and extract listing data
Includes Search-Grounded Research Mode for NOS/industrial equipment
"""
import os
import base64
import json
from pathlib import Path
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
        env_path = Path(__file__).resolve().parents[3] / ".env"
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
            self.client = None
            return

        # Initialize the new GenAI Client
        self.client = genai.Client(api_key=api_key)
        print("✅ AI Analyzer initialized (google-genai SDK)")




    
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
        
ROLE: You are an expert e-commerce specialist with deep knowledge of:
- Broadcast/video production equipment (cameras, switchers, routers, converters)
- Server hardware (Dell, HP, IBM blades, RAID controllers, memory modules)
- Industrial printing equipment (Xerox iGen, Fiery RIPs, print heads, toner)
- Networking equipment (Cisco, Juniper, fiber optic components)
- Test & measurement equipment (oscilloscopes, signal generators, analyzers)
- New Old Stock (NOS) - items that are factory-sealed or never used but manufactured years ago

CRITICAL IDENTIFICATION RULES:
1. READ ALL VISIBLE TEXT carefully: part numbers, model numbers, serial numbers, FCC IDs
2. For industrial equipment, the EXACT part number is more important than a generic product name
3. Look for OEM labels, asset tags, and specifications stickers
4. If item appears factory-sealed or unused, note "New Old Stock (NOS)" in condition
5. For server/IT parts: note capacity (GB, TB), speed (MHz, Gbps), form factor

OUTPUT FORMAT: Return a JSON object with this EXACT structure:
{
    "identification": {
        "brand": "exact brand name from label",
        "model": "exact model number (e.g., 'ROSS NK-3G64' or 'Dell PowerEdge R640')",
        "mpn": "manufacturer part number if visible (e.g., '0A36537' or 'CF081-67903')",
        "oem_part_numbers": ["list all visible OEM/alternative part numbers"],
        "serial_number": "if visible, otherwise null",
        "product_type": "specific item type (e.g., 'SDI Router', 'RAID Controller', 'Fuser Unit')",
        "compatible_systems": ["list systems this part works with if determinable"]
    },
    "condition": {
        "state": "New|New - Open Box|New Old Stock (NOS)|Used - Like New|Used - Good|Used - Acceptable|For Parts",
        "wear_level": "none|minimal|light|moderate|heavy",
        "is_nos": true/false,
        "factory_sealed": true/false,
        "accessories_visible": ["list", "any", "accessories"],
        "notes": "brief condition summary - for NOS, mention manufacturing date if visible"
    },
    "specifications": {
        "color": "main color",
        "dimensions": "if determinable",
        "technical_specs": {
            "capacity": "if applicable (e.g., '64GB', '4TB')",
            "speed": "if applicable (e.g., '3200MHz', '10Gbps')",
            "interface": "if applicable (e.g., 'SAS', 'PCIe', 'SDI')",
            "voltage": "if visible",
            "form_factor": "if applicable (e.g., '2.5-inch', '1U', 'Half-height')"
        },
        "other_specs": {"key": "value"}
    },
    "origin": {
        "country_of_manufacture": "if visible",
        "manufacturing_date": "if visible on label (important for NOS valuation)",
        "certifications": ["UL", "CE", "FCC", "etc"]
    },
    "listing": {
        "suggested_title": "Optimized 80-char Title: Brand Model PartNumber Keywords (Be specific!)",
        "description": "HTML_STRING",
        "suggested_price": "XX.XX",
        "price_reasoning": "For NOS/industrial: consider rarity, current availability, and B2B market rates"
    },
    "category_keywords": ["keyword1", "keyword2"],
    "ebay_category_suggestion": "Best eBay category path (e.g., 'Computers/Tablets > Enterprise Networking > Switches')"
}

INSTRUCTIONS FOR 'description' FIELD (HTML_STRING):
1. Use valid HTML tags: <h2>, <ul>, <li>, <b>, <br>, <p>.
2. Do NOT use <html>, <head>, or <body> tags.
3. Structure the description exactly like this:
   <h2>Product Overview</h2>
   <p>[Persuasive summary: what it is, what systems it works with, and accurate identification]</p>
   
   <h2>Condition</h2>
   <p><b>[State]</b>: [For NOS: note original packaging, seals, manufacturing date. For used: note wear honestly.]</p>
   
   <h2>Technical Specifications</h2>
   <ul>
     <li><b>Part Number:</b> [MPN]</li>
     <li><b>Compatible With:</b> [Systems]</li>
     <li>[Other relevant specs]</li>
   </ul>
   
   <h2>What's Included</h2>
   <ul>
     <li>[Item itself]</li>
     <li>[Any visible accessories/cables/manuals]</li>
   </ul>
   
   <h2>Shipping & Handling</h2>
   <p>Ships within 24 hours (Mon-Fri) from US warehouse. Professionally packed for safe arrival.</p>

4. TONE: Professional, technically accurate, B2B-friendly.
5. ACCURACY: Do not hallucinate specs or accessories not shown in photos."""


        # Prepare content: Modern GenAI SDK accepts text strings and PIL images directly
        from PIL import Image as PILImage
        
        contents = [prompt]  # Start with text prompt
        
        for path in image_paths:
            try:
                img = PILImage.open(path)
                contents.append(img)
            except Exception as e:
                print(f"⚠️ Could not load image {path}: {e}")
            
        try:
            if not self.client:
                 return {"error": "AI Client not initialized (Check API Key)"}

            # Config for JSON response
            config = types.GenerateContentConfig(
                temperature=0.3,
                top_p=0.95,
                max_output_tokens=4000,
                response_mime_type="application/json",
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                ]
            )

            # Use a stable model name
            model_name = 'gemini-2.0-flash'
            
            response = self.client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
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

    def research_part_number(self, brand: str, model: str, part_number: str = None) -> dict:
        """
        Use Google Search grounding to research an industrial part.
        
        Returns specs, pricing, and compatibility information from the web.
        """
        if not self.client:
            return {"error": "AI client not initialized", "researched": False}
        
        # Build search query
        search_terms = [brand, model]
        if part_number:
            search_terms.append(part_number)
        
        query = f"""Research this industrial equipment part for eBay listing:

Item: {' '.join(search_terms)}

Find and return:
1. EXACT product specifications (capacity, speed, interface, voltage)
2. What systems/equipment this is compatible with
3. Current market price range on eBay in 2026
4. Whether this is a rare/hard-to-find item
5. Common alternative part numbers

Return as JSON:
{{
    "product_name": "Full product name",
    "specifications": {{"key": "value"}},
    "compatible_with": ["system1", "system2"],
    "market_price": {{"low": 0, "mid": 0, "high": 0, "currency": "USD"}},
    "availability": "common|moderate|rare|very_rare",
    "alternative_part_numbers": [],
    "notes": "Any important details"
}}"""

        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.2,
                    response_mime_type="application/json"
                )
            )
            
            # Extract sources from grounding
            sources = []
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    for chunk in getattr(candidate.grounding_metadata, 'grounding_chunks', []) or []:
                        if hasattr(chunk, 'web') and chunk.web:
                            sources.append({
                                'title': chunk.web.title,
                                'url': chunk.web.uri
                            })
            
            # Parse response
            response_text = response.text
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
            
            research_data = json.loads(response_text.strip())
            research_data['sources'] = sources[:5]  # Keep top 5 sources
            research_data['researched'] = True
            
            print(f"🔍 Researched: {brand} {model} - Found {len(sources)} sources")
            return research_data
            
        except Exception as e:
            print(f"⚠️ Research failed: {e}")
            return {"error": str(e), "researched": False}

    def analyze_with_research(self, image_paths: list) -> dict:
        """
        Two-phase analysis: 
        1. Basic image analysis to extract identifiers
        2. Google Search research to enrich with specs and pricing
        3. Map to eBay item specifics and generate SEO title
        
        Best for NOS/industrial equipment where identification is complex.
        """
        # Phase 1: Basic analysis
        print("📸 Phase 1: Analyzing images...")
        basic_result = self.analyze_item(image_paths)
        
        if basic_result.get('error'):
            return basic_result
        

        # Phase 2: Research / Book Mode
        if self.client and basic_result.get('identification'):
            ident = basic_result['identification']
            brand = ident.get('brand', '')
            model = ident.get('model', '')
            mpn = ident.get('mpn', '')
            product_type = ident.get('product_type', '').lower()
            
            # --- BOOK MODE CHECK ---
            if "book" in product_type or "textbook" in product_type:
                print("📚 Detected Book! Attempting ISBN Scan...")
                from backend.app.services.isbn_scanner import ISBNScanner
                from backend.app.services.book_service import BookService
                
                isbn_scanner = ISBNScanner()
                isbn = None
                
                # Scan all images for ISBN
                for path in image_paths:
                    isbn = isbn_scanner.scan_image(path)
                    if isbn:
                        print(f"✅ Found ISBN: {isbn}")
                        break
                
                if isbn:
                    book_service = BookService()
                    book_data = book_service.lookup_isbn(isbn)
                    
                    if book_data.get('success'):
                        print(f"✅ Found Book Metadata: {book_data.get('title')}")
                        basic_result['book_metadata'] = book_data
                        basic_result['analysis_mode'] = 'book_scan'
                        
                        # Override identification with book data
                        basic_result['identification']['brand'] = book_data.get('publisher', 'Unknown')
                        basic_result['identification']['model'] = book_data.get('title')
                        basic_result['identification']['mpn'] = isbn
                        basic_result['identification']['product_type'] = 'Book'
                        
                        # Construct description
                        authors = ", ".join(book_data.get('authors', []))
                        desc = f"<h2>{book_data.get('title')}</h2>"
                        desc += f"<p><b>Author:</b> {authors}<br><b>Publisher:</b> {book_data.get('publisher')}<br><b>Year:</b> {book_data.get('publishedDate')}</p>"
                        desc += f"<p>{book_data.get('description', '')}</p>"
                        
                        basic_result['listing']['suggested_title'] = f"{book_data.get('title')} by {authors} ({book_data.get('publishedDate')[:4]}) {isbn}"
                        basic_result['listing']['description'] = desc
                        
                        return basic_result

            # --- END BOOK MODE ---

            if brand or model or mpn:
                print("🔍 Phase 2: Researching part...")
                research = self.research_part_number(brand, model, mpn)
                
                if research.get('researched'):
                    # Merge research into result
                    basic_result['research'] = research
                    
                    # Update price if research found better data
                    if research.get('market_price', {}).get('mid'):
                        market_mid = research['market_price']['mid']
                        basic_result['listing']['suggested_price'] = str(market_mid)
                        basic_result['listing']['price_reasoning'] = f"Based on market research: ${research['market_price']['low']}-${research['market_price']['high']}"
                    
                    # Add compatibility info to description if found
                    if research.get('compatible_with'):
                        basic_result['identification']['compatible_systems'] = research['compatible_with']
                    
                    print(f"✅ Enhanced with research data")
        
        # Phase 3: Map to eBay item specifics and generate SEO title
        try:
            from backend.app.services.item_specifics_mapper import ItemSpecificsMapper
            mapper = ItemSpecificsMapper()
            
            print("📋 Phase 3: Mapping to eBay item specifics...")
            basic_result['item_specifics'] = mapper.map_research_to_specifics(basic_result)
            basic_result['seo_title'] = mapper.generate_seo_title(basic_result)
            basic_result['condition_id'] = mapper.get_condition_id(basic_result.get('condition', {}))
            basic_result['condition_description'] = mapper.generate_condition_description(basic_result.get('condition', {}))
            print(f"✅ Generated {len(basic_result['item_specifics'])} item specifics")
        except Exception as e:
            print(f"⚠️ Item specifics mapping failed: {e}")
        
        basic_result['analysis_mode'] = 'research_enhanced' if basic_result.get('research') else 'basic'
        return basic_result


    def analyze_folder_with_research(self, folder_path):
        """Analyze folder with search-grounded research for industrial equipment"""
        images = self.get_images_from_folder(folder_path)
        
        if not images:
            return {"error": f"No images found in {folder_path}"}
        
        print(f"📸 Analyzing {len(images)} images from {Path(folder_path).name} (Research Mode)...")
        
        # Run enhanced analysis
        result = self.analyze_with_research(images)
        
        if result.get('error'):
            return result
            
        # Save result
        try:
            data_path = Path(folder_path) / 'ai_data.json'
            with open(data_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"✅ Saved research-enhanced analysis to {data_path.name}")
        except Exception as e:
            print(f"⚠️ Failed to save ai_data.json: {e}")
            
        return {
            'success': True,
            'data': result,
            'listing_id': None,
            'offer_id': None,
            'mode': result.get('analysis_mode', 'basic')
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
