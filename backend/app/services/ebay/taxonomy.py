"""
eBay Taxonomy Service
Handles category suggestions and item specifics metadata.
Includes a two-tier cache (in-memory + SQLite) to reduce API calls.
"""
import json
import time
import sqlite3
import requests
from collections import OrderedDict
from backend.app.services.ebay.policies import load_env, _get_headers
from backend.app.core.logger import get_logger

logger = get_logger('ebay_taxonomy')

TAXONOMY_URL = "https://api.ebay.com/commerce/taxonomy/v1"

# ── Cache Configuration ──────────────────────────────────────────────
TAXONOMY_CACHE_TTL_HOURS = 48
_MAX_MEMORY_CACHE = 500
_memory_cache = OrderedDict()  # {query_key: (data, timestamp)}


def _normalize_query(query: str) -> str:
    """Normalize a query for consistent cache keys."""
    return ' '.join(query.lower().strip().split())


def _get_db_path() -> str:
    from backend.app.core.paths import get_data_dir
    return str(get_data_dir() / "commander.db")


def _check_cache(cache_key: str):
    """Check in-memory cache, then SQLite. Returns cached data or None."""
    ttl_seconds = TAXONOMY_CACHE_TTL_HOURS * 3600
    now = time.time()

    # Tier 1: In-memory
    if cache_key in _memory_cache:
        data, ts = _memory_cache[cache_key]
        if now - ts < ttl_seconds:
            _memory_cache.move_to_end(cache_key)
            return data
        else:
            del _memory_cache[cache_key]

    # Tier 2: SQLite
    try:
        conn = sqlite3.connect(_get_db_path())
        cursor = conn.cursor()
        cursor.execute(
            "SELECT response_json, created_at FROM taxonomy_cache WHERE query_key = ?",
            (cache_key,)
        )
        row = cursor.fetchone()
        conn.close()

        if row and (now - row[1]) < ttl_seconds:
            data = json.loads(row[0])
            # Promote to memory cache
            _memory_cache[cache_key] = (data, row[1])
            if len(_memory_cache) > _MAX_MEMORY_CACHE:
                _memory_cache.popitem(last=False)
            return data
    except Exception as e:
        logger.debug(f"Cache read error: {e}")

    return None


def _save_cache(cache_key: str, data):
    """Write to both in-memory and SQLite caches."""
    now = time.time()

    # Tier 1: In-memory
    _memory_cache[cache_key] = (data, now)
    if len(_memory_cache) > _MAX_MEMORY_CACHE:
        _memory_cache.popitem(last=False)

    # Tier 2: SQLite
    try:
        conn = sqlite3.connect(_get_db_path())
        conn.execute(
            "INSERT OR REPLACE INTO taxonomy_cache (query_key, response_json, created_at) VALUES (?, ?, ?)",
            (cache_key, json.dumps(data), now)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"Cache write error: {e}")


def clear_taxonomy_cache():
    """Clear both in-memory and SQLite taxonomy caches."""
    _memory_cache.clear()
    try:
        conn = sqlite3.connect(_get_db_path())
        conn.execute("DELETE FROM taxonomy_cache")
        conn.commit()
        conn.close()
        logger.info("Taxonomy cache cleared")
    except Exception as e:
        logger.warning(f"Failed to clear taxonomy cache: {e}")


# ── Public API ────────────────────────────────────────────────────────

def get_suggested_category(query: str, limit: int = 1) -> dict:
    """
    Get suggested category for a query string.
    Results are cached for TAXONOMY_CACHE_TTL_HOURS.
    """
    if not query:
        return None

    cache_key = f"suggest:{_normalize_query(query)}:{limit}"
    cached = _check_cache(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for suggested category: {query[:40]}")
        return cached

    try:
        url = f"{TAXONOMY_URL}/category_tree/0/get_category_suggestions"
        headers = _get_headers()
        params = {
            'q': query,
            'limit': limit
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            suggestions = data.get('categorySuggestions', [])
            if suggestions:
                cat = suggestions[0].get('category', {})
                result = {
                    'id': cat.get('categoryId'),
                    'name': cat.get('categoryName'),
                    'path': _format_category_path(suggestions[0].get('categoryTreeNodeAncestors', []))
                }
                _save_cache(cache_key, result)
                return result
    except Exception as e:
        logger.warning(f"Category suggestion failed: {e}")

    return None

def get_safe_category(title: str) -> dict:
    """
    [DEPRECATED] Get category with 'Toner Trap' safety guard.
    AI now handles selection from eBay suggestions.
    Intercepts known hardware keywords and forces correct category.
    """
    title_lower = title.lower()

    # 1. HARDWARE KEYWORD GUARD
    # Corrected IDs after verification:
    # 51286 = Fusers
    # 51288 = Laser Drums
    # 170599 = Other Printer & Scanner Accs (Catch-all for belts, boards, etc)
    # 16204 = Toner Cartridges (AVOID THIS!)

    if "fuser" in title_lower:
        return {
            'id': '51286',
            'name': 'Fusers',
            'path': 'Computers/Tablets & Networking > Printers, Scanners & Supplies > Printer & Scanner Parts & Accs > Fusers',
            'source': 'guard_forced_fuser'
        }

    # "drum" is ambiguous (laser drum vs musical drum) — check for printer context
    if "drum" in title_lower and ("laser" in title_lower or "printer" in title_lower or "toner" in title_lower or "imaging" in title_lower):
        return {
            'id': '51288',
            'name': 'Laser Drums',
            'path': 'Computers/Tablets & Networking > Printers, Scanners & Supplies > Printer & Scanner Parts & Accs > Laser Drums',
            'source': 'guard_forced_drum'
        }

    # Context words that indicate the item is NOT a printer part
    non_hardware_context = ['game', 'toy', 'book', 'collectible', 'vintage', 'antique',
                            'shirt', 'shoe', 'clothing', 'figure', 'lego', 'card',
                            'vinyl', 'record', 'guitar', 'camera', 'phone', 'tablet',
                            'watch', 'jewelry', 'art', 'craft', 'kitchen', 'garden',
                            'sport', 'fishing', 'hunting', 'golf', 'bike', 'skateboard']
    has_non_hw_context = any(word in title_lower for word in non_hardware_context)

    # Only apply hardware guard if no contradicting context is present
    # Removed 'board' — too generic (matches board games, skateboards, etc.)
    hardware_keywords = ['belt', 'sensor', 'motor', 'gear', 'roller', 'assembly', 'maintenance kit', 'panel', 'guide']
    if not has_non_hw_context and any(word in title_lower for word in hardware_keywords):
        return {
            'id': '170599',
            'name': 'Other Printer & Scanner Accs',
            'path': 'Computers/Tablets & Networking > Printers, Scanners & Supplies > Printer & Scanner Parts & Accs > Other Printer & Scanner Accs',
            'source': 'guard_forced_general'
        }

    # 2. QUERY INJECTION
    # If not caught by guard, try to steer the AI away from Toner by appending context
    search_query = title
    if "xerox" in title_lower and "toner" not in title_lower:
        search_query += " REPLACEMENT PART"

    suggestion = get_suggested_category(search_query)

    if suggestion:
        suggestion['source'] = 'ebay_api'
        return suggestion

    return None

def _format_category_path(ancestors: list) -> str:
    path = [a.get('categoryName') for a in ancestors]
    return " > ".join(path)

def get_category_suggestions(query: str) -> list:
    """
    Get a list of category suggestions. Cached.
    """
    if not query:
        return []

    cache_key = f"suggestions:{_normalize_query(query)}"
    cached = _check_cache(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for category suggestions: {query[:40]}")
        return cached

    try:
        url = f"{TAXONOMY_URL}/category_tree/0/get_category_suggestions"
        headers = _get_headers()
        params = {'q': query}

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results = []
            for sug in data.get('categorySuggestions', []):
                cat = sug.get('category', {})
                results.append({
                    'category_id': cat.get('categoryId'),
                    'category_name': cat.get('categoryName'),
                    'full_path': _format_category_path(sug.get('categoryTreeNodeAncestors', [])) + " > " + cat.get('categoryName')
                })
            _save_cache(cache_key, results)
            return results
    except Exception as e:
        logger.warning(f"get_category_suggestions failed: {e}")

    return []

def get_item_aspects(category_id: str) -> dict:
    """
    Fetch required and optional item aspects for a given category. Cached.
    """
    if not category_id:
        return {"required": [], "optional": []}

    cache_key = f"aspects:{category_id}"
    cached = _check_cache(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for item aspects: category {category_id}")
        return cached

    try:
        url = f"{TAXONOMY_URL}/category_tree/0/get_item_aspects_for_category"
        headers = _get_headers()
        params = {'category_id': category_id}

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            aspects = data.get('aspects', [])

            required = []
            optional = []

            for a in aspects:
                constraint = a.get('aspectConstraint', {})
                aspect_info = {
                    "name": a.get('localizedAspectName'),
                    "usage": constraint.get('aspectUsage') or a.get('aspectUsage'),
                    "type": constraint.get('aspectDataType') or a.get('dataType'),
                    "values": [v.get('localizedValue') for v in a.get('aspectValues', []) or a.get('relevantAspectValues', [])]
                }

                if constraint.get('aspectRequired') or constraint.get('aspectUsage') == 'REQUIRED':
                    required.append(aspect_info)
                else:
                    optional.append(aspect_info)

            result = {"required": required, "optional": optional}
            _save_cache(cache_key, result)
            return result
    except Exception as e:
        logger.warning(f"get_item_aspects failed: {e}")

    return {"required": [], "optional": []}
