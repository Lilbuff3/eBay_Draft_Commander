"""
AI Price Estimator for Unique Items
Uses Gemini with Google Search grounding to estimate prices for items
that don't have direct eBay comparables.

Updated for 2026 google-genai SDK syntax.
"""
import os
import json
import base64
import statistics
from typing import Dict, List, Optional
from backend.app.core.constants import AI_PRICING_MODEL
from backend.app.core.logger import get_logger

logger = get_logger('ai_price')

from google import genai
from google.genai import types


class AIPriceEstimator:
    """
    Uses Gemini AI with Google Search grounding to estimate prices
    for unique items that don't have market comparables on eBay.
    """
    
    def __init__(self):
        self.client = None
        self._load_api_key()
    
    def _load_api_key(self):
        """Load Google API key from environment"""
        api_key = os.getenv('GOOGLE_API_KEY')
        
        if not api_key:
            logger.warning("[WARN] GOOGLE_API_KEY not found")
            return
        
        try:
            self.client = genai.Client(api_key=api_key)
            logger.info("[OK] AI Price Estimator initialized (google-genai SDK with Google Search)")
        except Exception as e:
            logger.error(f"[FAIL] google-genai init failed: {e}")
    
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
        if self.client:
            return self._estimate_with_search(query, condition, additional_context)
        return self._error_result("AI not initialized")
    
    def _estimate_with_search(self, query: str, condition: str, context: Optional[str]) -> Dict:
        """Estimate using new SDK with Google Search grounding"""
        prompt = self._build_prompt(query, condition, context)
        
        try:
            # Use google-genai SDK with Google Search tool
            # Using Gemini 3 Flash Preview for best price analysis with search
            response = self.client.models.generate_content(
                model=AI_PRICING_MODEL,  # Gemini 3 Flash Preview
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
            logger.error(f"[FAIL] Google Search grounding failed: {e}")
            # Try without search tool
            try:
                response = self.client.models.generate_content(
                    model=AI_PRICING_MODEL,
                    contents=prompt
                )
                return self._parse_response(response.text, query, [])
            except Exception as e2:
                return self._error_result(str(e2))
    
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
            logger.warning(f"[WARN] Failed to parse AI response: {e}")
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
                    'average': statistics.fmean(prices),
                    'median': statistics.median(prices),
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
    logger.info("Testing AI Price Estimator (2026 SDK)...")
    logger.info("=" * 50)
    
    estimator = AIPriceEstimator()
    
    # Test with a unique/rare item
    item = "Vintage 1960s Polaroid Land Camera Model 100"
    logger.info(f"\n[SEARCH] Estimating price for: {item}")
    
    result = estimator.estimate_price(item, condition="Used - Good")
    
    if result.get('success'):
        stats = result['stats']
        logger.info(f"\n[PRICE] Price Estimate:")
        logger.info(f"   Low:    ${stats['low']:.2f}")
        logger.info(f"   Mid:    ${stats['average']:.2f}")
        logger.info(f"   High:   ${stats['high']:.2f}")
        
        ai = result.get('ai_analysis', {})
        logger.info(f"\n[STATS] Confidence: {ai.get('confidence', 'unknown')}")
        
        if ai.get('reasoning'):
            logger.info(f"\n[INFO] Reasoning: {ai.get('reasoning')[:300]}...")
        
        if ai.get('comparable_items'):
            logger.info(f"\n[COMPS] Comparables:")
            for comp in ai['comparable_items'][:3]:
                logger.info(f"   • {comp}")
        
        if ai.get('search_sources'):
            logger.info(f"\n[LINK] Sources:")
            for src in ai['search_sources'][:3]:
                logger.info(f"   • {src}")
    else:
        logger.error(f"[FAIL] Error: {result.get('error')}")
    
    logger.info("\n[OK] Test complete!")
