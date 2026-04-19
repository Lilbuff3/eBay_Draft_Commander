"""
AI Image Analyzer for eBay Draft Commander
Uses Gemini to analyze product photos and extract listing data
Includes Search-Grounded Research Mode for NOS/industrial equipment
"""
import os
import base64
import json
from pathlib import Path
from google import genai
from google.genai import types

from backend.app.core.logger import get_logger
from backend.app.core.rate_limiter import limiter
from backend.app.core.constants import AI_MODEL_NAME
from backend.app.core.prompts import EBAY_LISTING_PROMPT, INDUSTRIAL_RESEARCH_PROMPT, ASPECT_ENRICHMENT_PROMPT

logger = get_logger('ai_analyzer')

class AIAnalyzer:
    """Analyzes product images using Gemini AI"""
    
    def __init__(self):
        """Initialize AI Analyzer with Google Gemini"""
        from dotenv import load_dotenv
        
        # Load .env file (searches parent directories automatically)
        load_dotenv()
        
        # Get API key from environment
        api_key = os.getenv('GOOGLE_API_KEY')
        
        if not api_key:
            logger.warning("GOOGLE_API_KEY not found in environment or .env file")
            self.client = None
            return

        # Initialize the new GenAI Client
        self.client = genai.Client(api_key=api_key)
        logger.info("AI Analyzer initialized (google-genai SDK)")




    
    def encode_image(self, image_path):
        """Encode image to base64"""
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            logger.warning(f"[WARN] Could not encode {image_path}: {e}")
            return None
    
    def get_images_from_folder(self, folder_path, max_images=None):
        """
        Get list of image file paths from a folder
        Args:
            folder_path: Path to folder containing images
            max_images: Maximum number of images (defaults to MAX_AI_IMAGES constant)
        """
        from backend.app.core.constants import MAX_AI_IMAGES
        if max_images is None:
            max_images = MAX_AI_IMAGES
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
    
    def analyze_item(self, image_paths, category_suggestions: str = ""):
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
        prompt = EBAY_LISTING_PROMPT.format(category_suggestions=category_suggestions)

        # Prepare content: Modern GenAI SDK accepts text strings and PIL images directly
        from PIL import Image as PILImage
        
        contents = [prompt]
        
        for path in image_paths:
            try:
                img = PILImage.open(path)
                contents.append(img)
            except Exception as e:
                logger.warning(f"Could not load image {path}: {e}")

        # Validate that at least one image was loaded (contents[0] is the prompt text)
        if len(contents) <= 1:
            return {"error": "No images could be loaded for analysis. Check that image files are valid."}

        try:
            if not self.client:
                 return {"error": "AI Client not initialized (Check API Key)"}

            # Config for JSON response
            config = types.GenerateContentConfig(
                temperature=0.2,
                top_p=0.95,
                max_output_tokens=4000,
                response_mime_type="application/json",
            )

            # Use Gemini Model from Config
            model_name = AI_MODEL_NAME
            
            # Apply Rate Limit for Gemini
            limiter.wait_if_needed('gemini')

            response = self.client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
            
            # Robust Response Parsing
            response_text = ""
            if hasattr(response, 'text') and response.text:
                response_text = response.text
            elif hasattr(response, 'candidates') and response.candidates:
                # Fallback to accessing first candidate parts
                try:
                     response_text = response.candidates[0].content.parts[0].text
                except (AttributeError, IndexError, KeyError) as e:
                     logger.debug(f"Could not extract text from response candidates: {e}")
            
            if not response_text:
                return {"error": "Empty response from AI", "raw": str(response)}

            logger.debug(f"Raw AI response text: {response_text[:200]}...")

            # Robust Pattern Matching for JSON
            import re
            # Match { ... } blocks, including nested braces
            # This is a simple regex, for complex cases a parser is better, but this handles most GenAI outputs
            json_pattern = r'(\{.*\})' 
            match = re.search(json_pattern, response_text, re.DOTALL)
            
            clean_text = response_text
            if match:
                clean_text = match.group(1)
            
            logger.debug(f"Cleaned AI response text: {clean_text[:200]}...")

            # Remove markdown code blocks if present (common in AI responses)
            clean_text = clean_text.replace('```json', '').replace('```', '').strip()

            try:
                data = json.loads(clean_text)
            except json.JSONDecodeError as e:
                # If regex failed, try to repair common issues or just logging
                logger.warning(f"JSON decode failed on cleaned text: {e}")
                # Try to find the first '{' and last '}' explicitly if regex failed
                start = response_text.find('{')
                end = response_text.rfind('}')
                if start != -1 and end != -1:
                    try:
                        data = json.loads(response_text[start:end+1])
                    except json.JSONDecodeError as e2:
                         logger.debug(f"Fallback JSON parsing also failed: {e2}")
                         return {"error": "Failed to parse JSON", "raw": response_text[:200]}
                else:
                    return {"error": "No JSON found in response", "raw": response_text[:200]}

            # Validate response structure
            if not isinstance(data, dict):
                if isinstance(data, list) and data:
                    data = data[0]
                
                # If STILL not a dict (or list was empty), it's invalid
                if not isinstance(data, dict):
                    return {"error": "AI returned invalid format (not a dict or list)", "raw": str(data)[:200]}
            
            # Validate required keys
            required_keys = ['identification', 'listing']
            missing = [k for k in required_keys if k not in data]
            if missing:
                logger.warning(f"AI response missing required keys: {missing}")
                return {
                    "error": f"AI response missing required keys: {missing}", 
                    "partial_data": data,
                    "raw": response_text[:300]
                }
            
            # Validate nested structure
            if not isinstance(data.get('listing'), dict):
                return {"error": "Invalid 'listing' structure (not a dict)", "data": data}
            if not isinstance(data.get('identification'), dict):
                return {"error": "Invalid 'identification' structure (not a dict)", "data": data}
            
            # Extract confidence_score if available, otherwise default to 0.85 
            # (or calculate based on response completeness)
            listing_sec = data.get('listing', {})
            if 'confidence_score' not in listing_sec:
                # Fallback: analyze response for basic completeness
                score = 0.90 if data.get('identification', {}).get('brand') else 0.80
                listing_sec['confidence_score'] = score

            # Add metadata
            data['image_paths'] = image_paths
            data['image_count'] = len(image_paths)
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return {"error": f"JSON parse error: {e}", "raw": response_text[:500]}
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {"error": str(e)}
    
    def enrich_item_specifics(self, image_paths: list, title: str, identification: dict,
                               category_name: str, aspect_schema: list,
                               existing_specifics: dict, research_specs=None) -> dict:
        """
        Second-pass AI call: fill in item specifics using the eBay aspect schema.

        This is a lightweight text+image call that passes the category's required
        and optional aspects (with allowed values) so the AI can fill them in
        accurately instead of guessing generic fields.

        Args:
            image_paths: Original product images (reused from analysis)
            title: Item title
            identification: Dict with brand/model/mpn from first AI pass
            category_name: eBay category name
            aspect_schema: List of aspect dicts from taxonomy API (each has name, isRequired, values)
            existing_specifics: Already-filled specifics (won't be overwritten)

        Returns:
            Dict of aspect_name -> value (merged with existing)
        """
        if not self.client or not aspect_schema:
            return existing_specifics

        # Build the aspect list text for the prompt
        aspect_lines = []
        for aspect in aspect_schema:
            name = aspect.get('name', '')
            required = aspect.get('isRequired', False)
            values = aspect.get('values', [])

            tag = "REQUIRED" if required else "recommended"
            if values:
                # Show first 20 allowed values to keep prompt size reasonable
                val_str = ", ".join(values[:20])
                if len(values) > 20:
                    val_str += f" ... ({len(values)} total)"
                aspect_lines.append(f"- [{tag}] {name}: Allowed values: [{val_str}]")
            else:
                aspect_lines.append(f"- [{tag}] {name}: (free text)")

        aspect_list_text = "\n".join(aspect_lines)

        # Build research specs section
        research_specs_section = ""
        if research_specs:
            specs_lines = [f"- {k}: {v}" for k, v in research_specs.items() if v]
            if specs_lines:
                research_specs_section = (
                    "WEB-VERIFIED SPECIFICATIONS (use these as ground truth, "
                    "more reliable than guessing):\n" + "\n".join(specs_lines)
                )

        # Format existing specifics
        existing_text = "\n".join(
            f"- {k}: {v}" for k, v in existing_specifics.items() if v
        ) or "(none filled yet)"

        prompt = ASPECT_ENRICHMENT_PROMPT.format(
            title=title,
            brand=identification.get('brand', 'Unknown'),
            model=identification.get('model', ''),
            mpn=identification.get('mpn', ''),
            category_name=category_name,
            research_specs_section=research_specs_section,
            aspect_list=aspect_list_text,
            existing_specifics=existing_text,
        )

        # Build content with images (reuse from first pass)
        from PIL import Image as PILImage
        contents = [prompt]
        for path in image_paths[:4]:  # Limit to 4 images to keep call fast
            try:
                img = PILImage.open(path)
                contents.append(img)
            except Exception:
                continue

        try:
            limiter.wait_if_needed('gemini')

            config = types.GenerateContentConfig(
                temperature=0.1,  # Low temp for factual extraction
                max_output_tokens=2000,
                response_mime_type="application/json",
            )

            response = self.client.models.generate_content(
                model=AI_MODEL_NAME,
                contents=contents,
                config=config,
            )

            text = response.text.strip() if response.text else "{}"
            # Clean markdown wrappers
            if text.startswith('```json'):
                text = text.split('```json')[1].split('```')[0]
            elif text.startswith('```'):
                text = text.split('```')[1].split('```')[0]

            enriched = json.loads(text.strip())

            if not isinstance(enriched, dict):
                logger.warning("Aspect enrichment returned non-dict")
                return existing_specifics

            # Merge: existing specifics take priority (don't overwrite user data)
            merged = dict(existing_specifics)
            for key, value in enriched.items():
                if key not in merged or not merged[key]:
                    # Truncate to eBay max
                    merged[key] = str(value)[:65]

            logger.info(f"Aspect enrichment added {len(merged) - len(existing_specifics)} new specifics")
            return merged

        except Exception as e:
            logger.warning(f"Aspect enrichment failed (non-fatal): {e}")
            return existing_specifics

    def analyze_folder(self, folder_path):
        """Analyze all images in a folder"""
        images = self.get_images_from_folder(folder_path)
        
        if not images:
            return {"error": f"No images found in {folder_path}"}
        
        logger.info(f"Analyzing {len(images)} images from {Path(folder_path).name}...")
        
        # Run analysis
        result = self.analyze_item(images)
        # Check for errors in result
        if result.get('error'):
            return result
            
        # Return success structure for queue manager
        return {
            'success': True,
            'data': result,
            'listing_id': None, # No listing created yet, just analysis
            'offer_id': None
        }

    def research_part_number(self, brand: str, model: str, part_number: str = None,
                             product_type: str = None, material: str = None,
                             condition: str = None) -> dict:
        """
        Use Google Search grounding to research a product.

        Returns specs, pricing, and compatibility information from the web.
        """
        if not self.client:
            return {"error": "AI client not initialized", "researched": False}

        # Build search query — include product_type and material for specificity
        search_parts = [brand]
        if material:
            search_parts.append(material)
        if product_type:
            search_parts.append(product_type)
        if model and model != product_type:
            search_parts.append(model)
        if part_number:
            search_parts.append(part_number)
        search_terms_str = " ".join(filter(None, search_parts))

        from datetime import datetime
        year = datetime.now().year

        # Format the prompt
        query = INDUSTRIAL_RESEARCH_PROMPT.format(
            search_terms=search_terms_str,
            product_type=product_type or "unknown",
            material=material or "unknown",
            condition=condition or "used",
            year=year
        )

        try:
            # Apply Rate Limit for Gemini
            limiter.wait_if_needed('gemini')

            response = self.client.models.generate_content(
                model=AI_MODEL_NAME,
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.2
                    # response_mime_type REMOVED
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
            response_text = response.text.strip() if response.text else "{}"
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
            
            import json
            try:
                research_data = json.loads(response_text.strip())
            except json.JSONDecodeError as e:
                logger.debug(f"Could not parse JSON from research response: {e}")
                research_data = {"error": "Could not parse JSON from research", "raw": response_text[:200]}
                
            research_data['sources'] = sources[:5]  # Keep top 5 sources
            research_data['researched'] = True
            
            logger.info(f"Researched: {brand} {model} - Found {len(sources)} sources")
            return research_data
            
        except Exception as e:
            logger.warning(f"Research failed: {e}")
            return {"error": str(e), "researched": False}

    def analyze_with_research(self, image_paths: list, category_suggestions: str = "") -> dict:
        """
        Two-phase analysis: 
        1. Basic image analysis to extract identifiers
        2. Google Search research to enrich with specs and pricing
        3. Map to eBay item specifics and generate SEO title
        
        Best for NOS/industrial equipment where identification is complex.
        """
        # Phase 1: Basic analysis
        logger.info("Phase 1: Analyzing images...")
        basic_result = self.analyze_item(image_paths, category_suggestions=category_suggestions)
        
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
                logger.info("Detected Book! Attempting ISBN Scan...")
                from backend.app.services.isbn_scanner import ISBNScanner
                from backend.app.services.book_service import BookService
                
                isbn_scanner = ISBNScanner()
                isbn = None
                
                # Scan all images for ISBN
                for path in image_paths:
                    isbn = isbn_scanner.scan_image(path)
                    if isbn:
                        logger.info(f"[OK] Found ISBN: {isbn}")
                        break
                
                if isbn:
                    book_service = BookService()
                    book_data = book_service.lookup_isbn(isbn)
                    
                    if book_data.get('success'):
                        logger.info(f"[OK] Found Book Metadata: {book_data.get('title')}")
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

            fast_mode = os.environ.get('FAST_MODE', 'false').lower() == 'true'
            if fast_mode:
                logger.info("Phase 2: SKIPPED (FAST_MODE=true)")

            if (brand or model or mpn) and not fast_mode:
                logger.info("Phase 2: Researching part...")
                material = ident.get('material', '')
                condition_state = basic_result.get('condition', {}).get('state', 'Used')
                research = self.research_part_number(
                    brand, model, mpn,
                    product_type=product_type,
                    material=material,
                    condition=condition_state
                )
                
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
                    
                    logger.info(f"[OK] Enhanced with research data")
        
        # Phase 3: Map to eBay item specifics and generate SEO title
        try:
            from backend.app.services.item_specifics_mapper import ItemSpecificsMapper
            mapper = ItemSpecificsMapper()
            
            logger.info("Phase 3: Mapping to eBay item specifics...")
            basic_result['item_specifics'] = mapper.map_research_to_specifics(basic_result)
            basic_result['seo_title'] = mapper.generate_seo_title(basic_result)
            basic_result['condition_id'] = mapper.get_condition_id(basic_result.get('condition', {}))
            basic_result['condition_description'] = mapper.generate_condition_description(basic_result.get('condition', {}))
            logger.info(f"[OK] Generated {len(basic_result['item_specifics'])} item specifics")
        except Exception as e:
            logger.warning(f"Item specifics mapping failed: {e}")
        
        basic_result['analysis_mode'] = 'research_enhanced' if basic_result.get('research') else 'basic'
        return basic_result


    def analyze_folder_with_research(self, folder_path):
        """Analyze folder with search-grounded research for industrial equipment"""
        images = self.get_images_from_folder(folder_path)
        
        if not images:
            return {"error": f"No images found in {folder_path}"}
        
        logger.info(f"Analyzing {len(images)} images from {Path(folder_path).name} (Research Mode)...")
        
        # Run enhanced analysis
        result = self.analyze_with_research(images)
        
        if result.get('error'):
            return result
            
        return {
            'success': True,
            'data': result,
            'listing_id': None,
            'offer_id': None,
            'mode': result.get('analysis_mode', 'basic')
        }


# Test the analyzer
if __name__ == "__main__":
    logger.info("Testing AI Analyzer...")
    
    analyzer = AIAnalyzer()
    
    # Test with sample images if available
    inbox = Path(__file__).parent / "inbox"
    
    if inbox.exists():
        folders = [f for f in inbox.iterdir() if f.is_dir()]
        
        if folders:
            logger.info(f"\nFound {len(folders)} item folders in inbox")
            
            # Analyze first folder
            result = analyzer.analyze_folder(folders[0])
            logger.info(json.dumps(result, indent=2))
        else:
            logger.info("\nNo item folders found in inbox/")
            logger.info("Create a folder and add photos to test")
    else:
        logger.info(f"\nInbox folder not found: {inbox}")
