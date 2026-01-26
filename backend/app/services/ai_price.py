"""
AI Price Estimator for Unique Items
Uses Gemini with Google Search grounding to estimate prices for items
that don't have direct eBay comparables.

Updated for 2026 google-genai SDK syntax.
"""
import os
import json
import base64
from pathlib import Path
from typing import Dict, List, Optional

# Try the NEW google-genai SDK first (2025+)
try:
    from google import genai
    from google.genai import types
    HAS_NEW_GENAI = True
except ImportError:
    HAS_NEW_GENAI = False

# Fall back to legacy google.generativeai if new SDK not available
if not HAS_NEW_GENAI:
    try:
        import google.generativeai as genai_legacy
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
        HAS_LEGACY_GENAI = True
    except ImportError:
        HAS_LEGACY_GENAI = False
        print("⚠️ Neither google-genai nor google.generativeai installed")
else:
    HAS_LEGACY_GENAI = False


class AIPriceEstimator:
    """
    Uses Gemini AI with Google Search grounding to estimate prices
    for unique items that don't have market comparables on eBay.
    """
    
    def __init__(self):
        self.client = None
        self.legacy_model = None
        self._load_api_key()
    
    def _load_api_key(self):
        """Load Google API key from .env"""
        env_path = Path(__file__).resolve().parents[3] / ".env"
        api_key = None
        
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('GOOGLE_API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        break
        
        if not api_key:
            api_key = os.getenv('GOOGLE_API_KEY')
        
        if not api_key:
            print("⚠️ GOOGLE_API_KEY not found")
            return
        
        # Initialize with NEW google-genai SDK (preferred)
        if HAS_NEW_GENAI:
            try:
                self.client = genai.Client(api_key=api_key)
                print("✅ AI Price Estimator initialized (google-genai SDK with Google Search)")
                return
            except Exception as e:
                print(f"⚠️ New SDK init failed: {e}, trying legacy...")
        
        # Fall back to legacy SDK
        if HAS_LEGACY_GENAI:
            try:
                genai_legacy.configure(api_key=api_key)
                self.legacy_model = genai_legacy.GenerativeModel('gemini-2.0-flash-exp')
                print("✅ AI Price Estimator initialized (legacy SDK, no live search)")
            except Exception as e:
                print(f"❌ Legacy SDK init failed: {e}")
    
    def estimate_price(
        self,
        query: str,
        condition: str = "Used",
        image_paths: Optional[List[str]] = None,
        additional_context: Optional[str] = None
    ) -> Dict:
        """
        Estimate price for an item using AI reasoning and Google Search.
        
        Args:
            query: Item description/name
            condition: Item condition (New, Used, etc.)
            image_paths: Optional list of image paths to analyze
            additional_context: Any extra info about the item
            
        Returns:
            Dict with price estimate, reasoning, and sources
        """
        # Try new SDK with Google Search first
        if self.client:
            return self._estimate_with_search(query, condition, additional_context)
        
        # Fall back to legacy SDK (no live search)
        if self.legacy_model:
            return self._estimate_legacy(query, condition, additional_context)
        
        return self._error_result("AI not initialized")
    
    def _estimate_with_search(self, query: str, condition: str, context: Optional[str]) -> Dict:
        """Estimate using new SDK with Google Search grounding"""
        prompt = self._build_prompt(query, condition, context)
        
        try:
            # Use google-genai SDK with Google Search tool
            # Using Gemini 3 Flash Preview for best price analysis with search
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',  # Stable Gemini 2.0 model
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            
            # Extract grounding metadata (sources)
            sources = []
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    metadata = candidate.grounding_metadata
                    for chunk in getattr(metadata, 'grounding_chunks', []) or []:
                        if hasattr(chunk, 'web') and chunk.web:
                            sources.append(f"{chunk.web.title}: {chunk.web.uri}")
            
            return self._parse_response(response.text, query, sources)
            
        except Exception as e:
            print(f"❌ Google Search grounding failed: {e}")
            # Try without search tool
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt
                )
                return self._parse_response(response.text, query, [])
            except Exception as e2:
                return self._error_result(str(e2))
    
    def _estimate_legacy(self, query: str, condition: str, context: Optional[str]) -> Dict:
        """Estimate using legacy SDK (no live search)"""
        prompt = self._build_prompt(query, condition, context)
        
        try:
            response = self.legacy_model.generate_content(prompt)
            return self._parse_response(response.text, query, [])
        except Exception as e:
            return self._error_result(str(e))
    
    def _build_prompt(self, query: str, condition: str, context: Optional[str]) -> str:
        """Build the price estimation prompt"""
        prompt = f"""You are an expert appraiser and e-commerce pricing specialist.

TASK: Research and estimate a fair selling price for this item on eBay.

ITEM: {query}
CONDITION: {condition}
{f"ADDITIONAL CONTEXT: {context}" if context else ""}

INSTRUCTIONS:
1. Search for actual market data for this item or similar items
2. Look for:
   - Current eBay listings and sold prices
   - Amazon prices for new items
   - Specialty retailer prices
   - Auction results for collectibles/antiques
3. Consider:
   - Brand reputation and rarity
   - Condition impact on price
   - Current market demand
   - Age and availability

RESPOND WITH THIS EXACT JSON STRUCTURE:
{{
    "estimate": {{
        "low": 0.00,
        "mid": 0.00,
        "high": 0.00,
        "currency": "USD"
    }},
    "confidence": "low|medium|high",
    "reasoning": "Detailed explanation of how you arrived at this price range",
    "comparable_items": [
        "Item 1 - $XX on Platform",
        "Item 2 - $XX on Platform"
    ],
    "value_factors": [
        "Factor that increases value",
        "Factor that decreases value"
    ],
    "pricing_notes": "Any special considerations"
}}

Be thorough. Base your estimate on real market data you find."""
        
        return prompt
    
    def _parse_response(self, text: str, query: str, sources: List[str]) -> Dict:
        """Parse the AI response into structured data"""
        try:
            # Clean up markdown code blocks if present
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0]
            elif '```' in text:
                parts = text.split('```')
                if len(parts) >= 2:
                    text = parts[1]
            
            data = json.loads(text.strip())
            
            # Normalize the response
            estimate = data.get('estimate', {})
            
            return {
                'success': True,
                'query': query,
                'source': 'ai_estimate',
                'stats': {
                    'low': float(estimate.get('low', 0)),
                    'average': float(estimate.get('mid', 0)),
                    'median': float(estimate.get('mid', 0)),
                    'high': float(estimate.get('high', 0)),
                    'sold': 0,  # AI estimate, no actual sales
                    'trend': 'neutral',
                    'trendPercent': 0
                },
                'items': [],
                'ai_analysis': {
                    'confidence': data.get('confidence', 'medium'),
                    'reasoning': data.get('reasoning', ''),
                    'comparable_items': data.get('comparable_items', []),
                    'value_factors': data.get('value_factors', []),
                    'search_sources': sources or data.get('search_sources', []),
                    'pricing_notes': data.get('pricing_notes', '')
                }
            }
            
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse AI response: {e}")
            return self._extract_from_text(text, query, sources)
        except Exception as e:
            return self._error_result(str(e))
    
    def _extract_from_text(self, text: str, query: str, sources: List[str]) -> Dict:
        """Fallback: Extract price info from unstructured text"""
        import re
        
        # Try to find price mentions
        prices = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
        prices = [float(p.replace('$', '').replace(',', '')) for p in prices]
        
        if prices:
            prices.sort()
            return {
                'success': True,
                'query': query,
                'source': 'ai_estimate',
                'stats': {
                    'low': prices[0],
                    'average': sum(prices) / len(prices),
                    'median': prices[len(prices) // 2],
                    'high': prices[-1],
                    'sold': 0,
                    'trend': 'neutral',
                    'trendPercent': 0
                },
                'items': [],
                'ai_analysis': {
                    'confidence': 'low',
                    'reasoning': text[:500],
                    'comparable_items': [],
                    'value_factors': [],
                    'search_sources': sources,
                    'pricing_notes': 'Extracted from unstructured AI response'
                }
            }
        
        return self._error_result("Could not extract price from AI response")
    
    def _error_result(self, error: str) -> Dict:
        """Return error result structure"""
        return {
            'success': False,
            'source': 'ai_estimate',
            'error': error,
            'stats': {
                'low': 0, 'average': 0, 'median': 0, 'high': 0,
                'sold': 0, 'trend': 'neutral', 'trendPercent': 0
            },
            'items': [],
            'ai_analysis': None
        }


# Test the estimator
if __name__ == "__main__":
    print("Testing AI Price Estimator (2026 SDK)...")
    print("=" * 50)
    
    estimator = AIPriceEstimator()
    
    # Test with a unique/rare item
    item = "Vintage 1960s Polaroid Land Camera Model 100"
    print(f"\n🔍 Estimating price for: {item}")
    
    result = estimator.estimate_price(item, condition="Used - Good")
    
    if result.get('success'):
        stats = result['stats']
        print(f"\n💰 Price Estimate:")
        print(f"   Low:    ${stats['low']:.2f}")
        print(f"   Mid:    ${stats['average']:.2f}")
        print(f"   High:   ${stats['high']:.2f}")
        
        ai = result.get('ai_analysis', {})
        print(f"\n📊 Confidence: {ai.get('confidence', 'unknown')}")
        
        if ai.get('reasoning'):
            print(f"\n💡 Reasoning: {ai.get('reasoning')[:300]}...")
        
        if ai.get('comparable_items'):
            print(f"\n📦 Comparables:")
            for comp in ai['comparable_items'][:3]:
                print(f"   • {comp}")
        
        if ai.get('search_sources'):
            print(f"\n🔗 Sources:")
            for src in ai['search_sources'][:3]:
                print(f"   • {src}")
    else:
        print(f"❌ Error: {result.get('error')}")
    
    print("\n✅ Test complete!")
