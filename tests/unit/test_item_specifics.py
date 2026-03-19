"""Tests for ItemSpecificsMapper book metadata mapping."""
import pytest
from backend.app.services.item_specifics_mapper import ItemSpecificsMapper


@pytest.fixture
def mapper():
    return ItemSpecificsMapper()


def _book_research(book_data):
    """Wrap book_data in the research_data structure the mapper expects."""
    return {'book_metadata': book_data}


class TestBookLanguageMapping:
    """Language should come from metadata, not be hardcoded to English."""

    def test_french_book(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'Le Petit Prince',
            'authors': ['Antoine de Saint-Exupery'],
            'publisher': 'Gallimard',
            'publishedDate': '1943-04-06',
            'language': 'fr',
            'categories': ['Fiction'],
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Language'] == 'French'

    def test_spanish_book(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'Cien Anos de Soledad',
            'authors': ['Gabriel Garcia Marquez'],
            'publisher': 'Editorial Sudamericana',
            'publishedDate': '1967-06-05',
            'language': 'es',
            'categories': ['Fiction'],
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Language'] == 'Spanish'

    def test_english_book(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'Some Book',
            'authors': ['Author'],
            'publisher': 'Publisher',
            'publishedDate': '2020-01-01',
            'language': 'en',
            'categories': ['Fiction'],
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Language'] == 'English'

    def test_missing_language_defaults_to_english(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'No Language Field',
            'authors': ['Author'],
            'publisher': 'Publisher',
            'publishedDate': '2020-01-01',
            'categories': ['Fiction'],
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Language'] == 'English'

    def test_unknown_language_code_uses_titlecase(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'Suomi Kirja',
            'authors': ['Author'],
            'publisher': 'Publisher',
            'publishedDate': '2020-01-01',
            'language': 'fi',
            'categories': ['Fiction'],
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Language'] == 'Fi'


class TestBookTopicMapping:
    """Topic should come from categories, not be hardcoded to Computers."""

    def test_fiction_category(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'A Novel',
            'authors': ['Author'],
            'publisher': 'Publisher',
            'publishedDate': '2020-01-01',
            'categories': ['Fiction'],
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Topic'] == 'Fiction'

    def test_history_category(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'History Book',
            'authors': ['Author'],
            'publisher': 'Publisher',
            'publishedDate': '2020-01-01',
            'categories': ['History', 'Military'],
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Topic'] == 'History'

    def test_no_categories_defaults_to_general(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'No Category Book',
            'authors': ['Author'],
            'publisher': 'Publisher',
            'publishedDate': '2020-01-01',
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Topic'] == 'General'


class TestBookFormatMapping:
    """Format should come from metadata, not be hardcoded to Paperback."""

    def test_hardcover_format(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'Hardcover Book',
            'authors': ['Author'],
            'publisher': 'Publisher',
            'publishedDate': '2020-01-01',
            'format': 'Hardcover',
            'categories': ['Fiction'],
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Format'] == 'Hardcover'

    def test_paperback_format(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'Paperback Book',
            'authors': ['Author'],
            'publisher': 'Publisher',
            'publishedDate': '2020-01-01',
            'format': 'Paperback',
            'categories': ['Fiction'],
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Format'] == 'Paperback'

    def test_missing_format_defaults_to_paperback(self, mapper):
        data = _book_research({
            'success': True,
            'title': 'No Format Book',
            'authors': ['Author'],
            'publisher': 'Publisher',
            'publishedDate': '2020-01-01',
            'categories': ['Fiction'],
        })
        specifics = mapper.map_research_to_specifics(data)
        assert specifics['Format'] == 'Paperback'


"""Tests for two-pass item specifics enrichment."""
from unittest.mock import patch, MagicMock, PropertyMock


class TestAspectEnrichment:
    """AI enrichment fills in eBay-required aspects from images + schema."""

    def test_enrichment_merges_without_overwriting(self):
        """New aspects are added but existing ones are preserved."""
        from backend.app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        analyzer.client = None  # Disabled client returns existing

        existing = {"Brand": "Xerox", "MPN": "108R00713"}
        result = analyzer.enrich_item_specifics(
            image_paths=[], title="Test", identification={},
            category_name="Toner", aspect_schema=[], existing_specifics=existing,
        )
        assert result == existing  # No client -> passthrough

    def test_enrichment_returns_existing_on_empty_schema(self):
        """Empty aspect schema -> skip enrichment, return existing."""
        from backend.app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        analyzer.client = MagicMock()

        existing = {"Brand": "Test"}
        result = analyzer.enrich_item_specifics(
            image_paths=[], title="Test", identification={},
            category_name="", aspect_schema=[], existing_specifics=existing,
        )
        assert result == existing

    @patch("backend.app.services.ai_analyzer.limiter")
    def test_enrichment_adds_new_fields(self, mock_limiter):
        """When AI returns new aspects, they are merged in."""
        from backend.app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        mock_client = MagicMock()
        analyzer.client = mock_client

        # Simulate AI returning new aspects
        mock_response = MagicMock()
        type(mock_response).text = PropertyMock(return_value='{"Color": "Cyan", "Brand": "Should Not Overwrite"}')
        mock_client.models.generate_content.return_value = mock_response

        existing = {"Brand": "Xerox"}
        schema = [
            {"name": "Color", "isRequired": True, "values": ["Cyan", "Magenta", "Yellow", "Black"]},
            {"name": "Brand", "isRequired": True, "values": []},
        ]

        result = analyzer.enrich_item_specifics(
            image_paths=[], title="Xerox Ink", identification={"brand": "Xerox"},
            category_name="Toner Cartridges", aspect_schema=schema, existing_specifics=existing,
        )
        assert result["Color"] == "Cyan"
        assert result["Brand"] == "Xerox"  # NOT overwritten

    @patch("backend.app.services.ai_analyzer.limiter")
    def test_enrichment_truncates_long_values(self, mock_limiter):
        """Values longer than 65 chars are truncated."""
        from backend.app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        mock_client = MagicMock()
        analyzer.client = mock_client

        long_value = "A" * 100
        mock_response = MagicMock()
        type(mock_response).text = PropertyMock(return_value=f'{{"Type": "{long_value}"}}')
        mock_client.models.generate_content.return_value = mock_response

        schema = [{"name": "Type", "isRequired": False, "values": []}]
        result = analyzer.enrich_item_specifics(
            image_paths=[], title="Test", identification={},
            category_name="Test", aspect_schema=schema, existing_specifics={},
        )
        assert len(result["Type"]) == 65
