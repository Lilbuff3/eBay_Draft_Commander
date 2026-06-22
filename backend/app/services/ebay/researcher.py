"""
eBay Price Researcher

1. Primary: eBay Browse API (condition-filtered active listings)
2. Secondary: AI-powered estimation for unique items (Gemini + Google Search)
3. Fallback: HTML scraping (unreliable due to bot protection)
"""
import requests
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Dict, Optional
import urllib.parse
from backend.app.core.logger import get_logger

logger = get_logger('ebay_researcher')

# Import the official API client
try:
    from backend.app.services.ebay.browse import eBayBrowseAPI
    HAS_BROWSE_API = True
except ImportError:
    HAS_BROWSE_API = False
    logger.warning("ebay_browse_api not found, using scraper fallback only")

# Import AI price estimator
try:
    from backend.app.services.ai_price import AIPriceEstimator
    HAS_AI_ESTIMATOR = True
except ImportError:
    HAS_AI_ESTIMATOR = False
    logger.warning("ai_price_estimator not found, AI fallback disabled")


@dataclass
class SoldItem:
    title: str
    price: float
    shipping: float
    date: str
    condition: str
    url: str
    image_url: str = "" # Added image_url support


class eBayResearcher:
    """
    Research pricing on eBay using the official Browse API.
    Falls back to scraping if API is unavailable (unreliable).
    """
    
    def __init__(self, use_api: bool = True, use_ai: bool = True):
        """
        Initialize the researcher.
        
        Args:
            use_api: If True, prefer Browse API. If False, use scraper only.
            use_ai: If True, use AI for unique items without comparables.
        """
        self._api_client = None
        self._ai_estimator = None
        self._use_api = use_api and HAS_BROWSE_API
        self._use_ai = use_ai and HAS_AI_ESTIMATOR
        
        if self._use_api:
            try:
                self._api_client = eBayBrowseAPI()
            except Exception as e:
                logger.warning(f"Browse API init failed: {e}")
                self._use_api = False
        
        if self._use_ai:
            try:
                self._ai_estimator = AIPriceEstimator()
            except Exception as e:
                logger.warning(f"AI Estimator init failed: {e}")
                self._use_ai = False

    def search_sold(self, query: str, limit: int = 30, use_ai_fallback: bool = True, condition: str = None) -> Dict:
        """
        Search for pricing data on similar items.

        Args:
            query: Search keywords
            limit: Max items to retrieve
            use_ai_fallback: Use AI estimation if no market data found
            condition: Optional condition enum for Browse API filtering

        Returns:
            Dict with 'stats', 'items', and 'source' keys
        """
        if not query:
            return {'stats': {}, 'items': [], 'source': 'none'}

        # Try Browse API first (preferred)
        if self._use_api and self._api_client:
            try:
                result = self._api_client.search_items(query, limit, condition=condition)
                if result['items']:  # Got results
                    return result
            except Exception as e:
                logger.warning(f"Browse API failed, trying fallbacks: {e}")
        
        # Try AI estimation for unique items (if enabled)
        if use_ai_fallback and self._use_ai and self._ai_estimator:
            try:
                logger.info(f"No market data found, using AI estimation for: {query}")
                result = self._ai_estimator.estimate_price(query)
                if result.get('success') and result['stats'].get('average', 0) > 0:
                    return result
            except Exception as e:
                logger.error(f"AI estimation failed: {e}")
        
        # No scraper fallback anymore. If both Browse API and AI estimation fail, return empty structure.
        return {
            'stats': {
                'average': 0, 'median': 0, 'low': 0, 'high': 0,
                'sold': 0, 'trend': 'neutral', 'trendPercent': 0
            },
            'items': [],
            'source': 'none'
        }

    def _item_to_dict(self, item: SoldItem) -> Dict:
        """Convert SoldItem to dict"""
        return {
            'title': item.title,
            'price': item.price,
            'shipping': item.shipping,
            'date': item.date,
            'soldDate': item.date, # Alias for frontend
            'condition': item.condition,
            'url': item.url,
            'imageUrl': item.image_url # CamelCase for frontend
        }


# Test
if __name__ == "__main__":
    logger.info("Testing eBay Researcher...")
    logger.info("=" * 50)
    
    researcher = eBayResearcher()
    result = researcher.search_sold("vintage camera")
    
    logger.info(f"\nSource: {result.get('source', 'unknown')}")
    logger.info(f"Found {len(result['items'])} items")
    
    stats = result['stats']
    if stats.get('average', 0) > 0:
        logger.info(f"Average: ${stats['average']:.2f}")
        logger.info(f"Median:  ${stats['median']:.2f}")
        logger.info(f"Range:   ${stats['low']:.2f} - ${stats['high']:.2f}")
    else:
        logger.info("No pricing data available")

