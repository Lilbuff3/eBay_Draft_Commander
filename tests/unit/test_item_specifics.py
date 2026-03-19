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
