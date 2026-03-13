"""
eBay Draft Commander MCP Server

Exposes read-only eBay API tools for interactive debugging,
market research, and listing management via Claude Code.

Uses the official MCP Python SDK (mcp.server.fastmcp.FastMCP).
Wraps existing eBay service modules — no new API logic.

Tools:
  - ebay_search: Search active eBay listings (Browse API)
  - ebay_category_suggest: Get category suggestions for a query
  - ebay_get_aspects: Get item aspects for a category ID
  - ebay_price_research: Research pricing for similar items
  - ebay_active_listings: List seller's active listings
  - ebay_token_status: Check eBay API token health
"""
import sys
import os
import json
from pathlib import Path

# Ensure the project root is on sys.path so backend.* imports work
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env before any backend imports
from backend.config import Config, load_dotenv_manually
load_dotenv_manually(Path(__file__).parent)

from mcp.server.fastmcp import FastMCP

# Create the MCP server
mcp = FastMCP(
    name="eBay Draft Commander",
    instructions=(
        "eBay API tools for the Draft Commander project. "
        "All tools are read-only — no listings are created or modified. "
        "Use these to research pricing, look up categories, check token status, "
        "and inspect active listings."
    ),
)


@mcp.tool()
def ebay_search(query: str, limit: int = 10) -> str:
    """Search active eBay listings for pricing data.

    Uses the Browse API (client credentials auth) to find current listings
    matching the query. Returns pricing statistics and item details.

    Args:
        query: Search keywords (e.g., "vintage leather jacket")
        limit: Max items to return (default 10, max 30)
    """
    try:
        from backend.app.services.ebay.browse import eBayBrowseAPI

        limit = min(max(1, limit), 30)
        client = eBayBrowseAPI()
        result = client.search_items(query, limit=limit)

        if not result or not result.get("items"):
            return json.dumps({"message": f"No results found for '{query}'", "stats": {}})

        # Trim items to requested limit for cleaner output
        result["items"] = result["items"][:limit]
        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def ebay_category_suggest(query: str) -> str:
    """Get eBay category suggestions for a product description.

    Uses the Taxonomy API to find the best matching eBay category.
    Results are cached for 48 hours.

    Args:
        query: Product description or title (e.g., "Harry Potter hardcover book")
    """
    try:
        from backend.app.services.ebay.taxonomy import get_category_suggestions

        suggestions = get_category_suggestions(query)
        if not suggestions:
            return json.dumps({"message": f"No category suggestions for '{query}'"})

        return json.dumps(suggestions, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def ebay_get_aspects(category_id: str) -> str:
    """Get required and optional item aspects (specifics) for an eBay category.

    Returns the aspect schema including required fields, allowed values,
    and data types. Cached for 48 hours.

    Args:
        category_id: eBay category ID (e.g., "261186" for Books)
    """
    try:
        from backend.app.services.ebay.taxonomy import get_item_aspects

        aspects = get_item_aspects(str(category_id))
        if not aspects or (not aspects.get("required") and not aspects.get("optional")):
            return json.dumps({"message": f"No aspects found for category {category_id}"})

        # Add summary counts
        result = {
            "category_id": category_id,
            "required_count": len(aspects.get("required", [])),
            "optional_count": len(aspects.get("optional", [])),
            "required": aspects.get("required", []),
            "optional": aspects.get("optional", []),
        }
        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def ebay_price_research(query: str, limit: int = 10) -> str:
    """Research pricing for similar items on eBay.

    Uses a multi-source cascade: Browse API search, then AI estimation
    as fallback. Returns pricing statistics (avg, median, low, high)
    and comparable items.

    Args:
        query: Product description for price research
        limit: Max comparable items to return (default 10, max 30)
    """
    try:
        from backend.app.services.ebay.researcher import eBayResearcher

        limit = min(max(1, limit), 30)
        researcher = eBayResearcher(use_api=True, use_ai=False)
        result = researcher.search_sold(query, limit=limit, use_ai_fallback=False)

        if not result or result.get("source") == "error":
            return json.dumps({"message": f"No pricing data found for '{query}'"})

        result["items"] = result.get("items", [])[:limit]
        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def ebay_active_listings(limit: int = 20) -> str:
    """List the seller's active eBay listings.

    Uses the Trading API (GetSellerList) to fetch current active listings.
    Returns listing details including title, price, SKU, and status.

    Args:
        limit: Max listings to return (default 20)
    """
    try:
        from backend.app.services.ebay.trading import TradingService

        trading = TradingService()
        result, status_code = trading.get_active_listings_light()

        if status_code != 200:
            return json.dumps({"error": result.get("error", "Failed to fetch listings")})

        listings = result.get("listings", [])[:limit]
        return json.dumps(
            {
                "total": result.get("total", len(listings)),
                "showing": len(listings),
                "source": result.get("source", "trading_api"),
                "listings": listings,
            },
            indent=2,
            default=str,
        )

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def ebay_token_status() -> str:
    """Check eBay API token health and expiry status.

    Returns whether a valid access token exists, when it expires,
    and whether refresh credentials are configured.
    """
    try:
        from backend.app.core.token_manager import get_token_manager

        tm = get_token_manager()
        status = tm.get_token_status()
        return json.dumps(status, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()
