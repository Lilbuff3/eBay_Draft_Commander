"""
Tests for category taxonomy guards and caching.

Tests two modules:
1. backend.app.services.ebay.taxonomy — get_safe_category() guard logic,
   _normalize_query(), _check_cache(), _save_cache(), clear_taxonomy_cache()
2. backend.app.services.category_mapper — CategoryMapper.get_category()

Guard logic in get_safe_category() is pure string matching that returns
immediately without API calls, so those tests need no mocking. Tests that
fall through to get_suggested_category() mock it to avoid real API calls.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from backend.app.services.ebay.taxonomy import (
    get_safe_category,
    _normalize_query,
    _check_cache,
    _save_cache,
    clear_taxonomy_cache,
    _memory_cache,
    _MAX_MEMORY_CACHE,
    TAXONOMY_CACHE_TTL_HOURS,
)
from backend.app.services.category_mapper import CategoryMapper


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_cache():
    """Ensure the module-level memory cache is empty before and after each test."""
    _memory_cache.clear()
    yield
    _memory_cache.clear()


@pytest.fixture
def mapper():
    """Create a CategoryMapper instance."""
    return CategoryMapper()


# ── TestGetSafeCategory ──────────────────────────────────────────────


class TestGetSafeCategory:
    """Tests for the hardware keyword guards in get_safe_category().

    The guards are pure string matching on the title and return immediately.
    Only tests where the title falls through all guards need to mock
    get_suggested_category.
    """

    # -- Fuser guard --------------------------------------------------

    def test_fuser_forces_51286(self):
        """Any title containing 'fuser' should be forced to category 51286."""
        result = get_safe_category("Xerox Fuser Unit")
        assert result['id'] == '51286'
        assert result['source'] == 'guard_forced_fuser'
        assert result['name'] == 'Fusers'

    # -- Drum guard (requires printer context) ------------------------

    def test_drum_with_laser_context_forces_51288(self):
        """'drum' + 'laser' context should force category 51288."""
        result = get_safe_category("HP LaserJet Drum")
        assert result['id'] == '51288'
        assert result['source'] == 'guard_forced_drum'

    def test_drum_with_printer_context_forces_51288(self):
        """'drum' + 'printer' context should force category 51288."""
        result = get_safe_category("Printer Drum Unit")
        assert result['id'] == '51288'
        assert result['source'] == 'guard_forced_drum'

    def test_drum_with_toner_context_forces_51288(self):
        """'drum' + 'toner' context should force category 51288."""
        result = get_safe_category("Compatible Toner Drum")
        assert result['id'] == '51288'
        assert result['source'] == 'guard_forced_drum'

    def test_drum_with_imaging_context_forces_51288(self):
        """'drum' + 'imaging' context should force category 51288."""
        result = get_safe_category("Imaging Drum Unit")
        assert result['id'] == '51288'
        assert result['source'] == 'guard_forced_drum'

    @patch('backend.app.services.ebay.taxonomy.get_suggested_category')
    def test_drum_without_context_falls_through(self, mock_suggest):
        """'drum' without printer context (e.g. musical drum) should NOT
        trigger the drum guard and should fall through to the API."""
        mock_suggest.return_value = {'id': '180015', 'name': 'Drums'}
        result = get_safe_category("Yamaha Snare Drum")
        mock_suggest.assert_called_once()
        assert result['source'] == 'ebay_api'

    # -- Generic hardware guard (with non-hardware exclusion) ---------

    def test_hardware_belt_forces_170599(self):
        """'belt' without non-hardware context should force 170599."""
        result = get_safe_category("Transfer Belt Assembly")
        assert result['id'] == '170599'
        assert result['source'] == 'guard_forced_general'

    def test_hardware_sensor_forces_170599(self):
        """'sensor' without non-hardware context should force 170599."""
        result = get_safe_category("Paper Sensor Module")
        assert result['id'] == '170599'
        assert result['source'] == 'guard_forced_general'

    def test_hardware_roller_forces_170599(self):
        """'roller' without non-hardware context should force 170599."""
        result = get_safe_category("Pickup Roller Kit")
        assert result['id'] == '170599'
        assert result['source'] == 'guard_forced_general'

    # -- Non-hardware context prevents guard --------------------------

    @patch('backend.app.services.ebay.taxonomy.get_suggested_category')
    def test_non_hardware_context_guitar_prevents_guard(self, mock_suggest):
        """'guitar' in title should prevent the hardware guard from firing
        even though 'gear' is a hardware keyword."""
        mock_suggest.return_value = {'id': '41405', 'name': 'Guitar Effects'}
        result = get_safe_category("Guitar Gear Pedal")
        assert result['id'] != '170599'
        mock_suggest.assert_called_once()

    @patch('backend.app.services.ebay.taxonomy.get_suggested_category')
    def test_non_hardware_context_game_prevents_guard(self, mock_suggest):
        """'game' and 'book' in title should prevent the hardware guard
        even though 'guide' is a hardware keyword."""
        mock_suggest.return_value = {'id': '2536', 'name': 'Board Games'}
        result = get_safe_category("Board Game Guide Book")
        assert result['id'] != '170599'
        mock_suggest.assert_called_once()

    @patch('backend.app.services.ebay.taxonomy.get_suggested_category')
    def test_non_hardware_context_skateboard_prevents_guard(self, mock_suggest):
        """'skateboard' in title should prevent the hardware guard
        even though 'roller' is a hardware keyword."""
        mock_suggest.return_value = {'id': '36612', 'name': 'Skateboard Parts'}
        result = get_safe_category("Skateboard Roller Bearings")
        assert result['id'] != '170599'
        mock_suggest.assert_called_once()

    # -- Xerox query injection ----------------------------------------

    @patch('backend.app.services.ebay.taxonomy.get_suggested_category')
    def test_xerox_query_injection(self, mock_suggest):
        """Xerox titles without 'toner' should have ' REPLACEMENT PART'
        appended to the search query sent to get_suggested_category."""
        mock_suggest.return_value = {'id': '170599', 'name': 'Printer Parts'}
        get_safe_category("Xerox WorkCentre Part")
        args, _ = mock_suggest.call_args
        assert args[0] == "Xerox WorkCentre Part REPLACEMENT PART"

    @patch('backend.app.services.ebay.taxonomy.get_suggested_category')
    def test_xerox_toner_no_injection(self, mock_suggest):
        """Xerox titles that include 'toner' should NOT get the
        ' REPLACEMENT PART' suffix."""
        mock_suggest.return_value = {'id': '16204', 'name': 'Toner Cartridges'}
        get_safe_category("Xerox Toner Cartridge")
        args, _ = mock_suggest.call_args
        assert args[0] == "Xerox Toner Cartridge"

    # -- API returns None ---------------------------------------------

    @patch('backend.app.services.ebay.taxonomy.get_suggested_category')
    def test_api_returns_none(self, mock_suggest):
        """When get_suggested_category returns None, get_safe_category
        should also return None."""
        mock_suggest.return_value = None
        result = get_safe_category("Some Obscure Item Title")
        assert result is None


# ── TestCategoryMapper ───────────────────────────────────────────────


class TestCategoryMapper:
    """Tests for CategoryMapper.get_category() business logic layer."""

    def test_guard_forced_generates_warning(self, mapper):
        """When get_safe_category returns a guard-forced result, the mapper
        should set a warning explaining the forced category."""
        with patch('backend.app.services.category_mapper.get_safe_category') as mock_safe:
            mock_safe.return_value = {
                'id': '51286',
                'name': 'Fusers',
                'source': 'guard_forced_fuser',
            }
            result = mapper.get_category("Xerox Fuser Unit")
            assert result['id'] == '51286'
            assert result['warning'] is not None
            assert 'forced' in result['warning'].lower() or 'Fusers' in result['warning']

    def test_api_source_no_warning(self, mapper):
        """When get_safe_category returns an ebay_api source, there should
        be no warning."""
        with patch('backend.app.services.category_mapper.get_safe_category') as mock_safe:
            mock_safe.return_value = {
                'id': '12345',
                'name': 'Some Category',
                'source': 'ebay_api',
            }
            result = mapper.get_category("Normal Item")
            assert result['id'] == '12345'
            assert result['warning'] is None

    def test_exception_returns_empty(self, mapper):
        """When get_safe_category raises an exception, the mapper should
        return a safe empty result with id=None and source='none'."""
        with patch('backend.app.services.category_mapper.get_safe_category') as mock_safe:
            mock_safe.side_effect = Exception("API timeout")
            result = mapper.get_category("Broken Item")
            assert result['id'] is None
            assert result['source'] == 'none'

    def test_no_suggestion_returns_empty(self, mapper):
        """When get_safe_category returns None, the mapper should return
        a result with id=None."""
        with patch('backend.app.services.category_mapper.get_safe_category') as mock_safe:
            mock_safe.return_value = None
            result = mapper.get_category("Unknown Item")
            assert result['id'] is None
            assert result['source'] == 'none'


# ── TestTaxonomyCache ────────────────────────────────────────────────


class TestTaxonomyCache:
    """Tests for the taxonomy caching layer: _normalize_query, _check_cache,
    _save_cache, and clear_taxonomy_cache.

    These tests directly manipulate the module-level _memory_cache and mock
    sqlite3.connect to avoid real database access.
    """

    # -- _normalize_query ---------------------------------------------

    def test_normalize_query(self):
        """Should lowercase, strip, and collapse whitespace."""
        assert _normalize_query("  Mixed  CASE  ") == "mixed case"

    def test_normalize_query_extra_spaces(self):
        """Multiple spaces between words should collapse to single spaces."""
        assert _normalize_query("hello   world") == "hello world"

    # -- _check_cache (memory tier) -----------------------------------

    @patch('backend.app.services.ebay.taxonomy.sqlite3')
    def test_memory_cache_hit(self, mock_sqlite3):
        """Pre-populated memory cache entries within TTL should be returned."""
        _memory_cache['test_key'] = ({'id': '123', 'name': 'Test'}, time.time())
        result = _check_cache('test_key')
        assert result == {'id': '123', 'name': 'Test'}
        # SQLite should not be consulted when memory cache hits
        mock_sqlite3.connect.assert_not_called()

    @patch('backend.app.services.ebay.taxonomy.sqlite3')
    def test_memory_cache_miss(self, mock_sqlite3):
        """Empty memory cache should return None (with SQLite also returning nothing)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite3.connect.return_value = mock_conn
        result = _check_cache('nonexistent_key')
        assert result is None

    @patch('backend.app.services.ebay.taxonomy.sqlite3')
    def test_memory_cache_expiry(self, mock_sqlite3):
        """Entries older than TAXONOMY_CACHE_TTL_HOURS should be treated as
        expired: return None and remove the entry from memory cache."""
        expired_ts = time.time() - (TAXONOMY_CACHE_TTL_HOURS * 3600 + 1)
        _memory_cache['expired_key'] = ({'id': '999'}, expired_ts)

        # Mock SQLite to also return nothing
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite3.connect.return_value = mock_conn

        result = _check_cache('expired_key')
        assert result is None
        assert 'expired_key' not in _memory_cache

    # -- _save_cache --------------------------------------------------

    @patch('backend.app.services.ebay.taxonomy.sqlite3')
    def test_cache_eviction(self, mock_sqlite3):
        """When the memory cache exceeds _MAX_MEMORY_CACHE, the oldest
        entry (FIFO) should be evicted."""
        mock_conn = MagicMock()
        mock_sqlite3.connect.return_value = mock_conn

        # Fill cache to exactly _MAX_MEMORY_CACHE
        for i in range(_MAX_MEMORY_CACHE):
            _memory_cache[f'key_{i}'] = ({'id': str(i)}, time.time())

        # Saving one more should evict the oldest (key_0)
        _save_cache('new_key', {'id': 'new'})
        assert 'key_0' not in _memory_cache
        assert 'new_key' in _memory_cache
        assert len(_memory_cache) == _MAX_MEMORY_CACHE

    # -- clear_taxonomy_cache -----------------------------------------

    @patch('backend.app.services.ebay.taxonomy.sqlite3')
    def test_clear_cache(self, mock_sqlite3):
        """clear_taxonomy_cache should empty the memory cache entirely."""
        mock_conn = MagicMock()
        mock_sqlite3.connect.return_value = mock_conn

        _memory_cache['a'] = ({'id': '1'}, time.time())
        _memory_cache['b'] = ({'id': '2'}, time.time())
        assert len(_memory_cache) == 2

        clear_taxonomy_cache()
        assert len(_memory_cache) == 0
