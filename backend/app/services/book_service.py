
import os
import requests
from typing import Dict
from backend.app.core.logger import get_logger

logger = get_logger('book_service')

class BookService:
    """
    Fetches book metadata by ISBN: Google Books first (keyed — anonymous
    access gets a tiny IP quota and 429s during batch scanning), with an
    Open Library fallback so one throttled provider doesn't stop a session.
    """

    GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
    OPEN_LIBRARY_API = "https://openlibrary.org/api/books"

    def lookup_isbn(self, isbn: str) -> Dict:
        """
        Lookup book details by ISBN.

        Args:
            isbn: ISBN-10 or ISBN-13 string (digits only)

        Returns:
            Dict with title, authors, publisher, publishedDate, description, thumbnail
        """
        result = self._lookup_google(isbn)
        if result.get('success'):
            return result
        fallback = self._lookup_open_library(isbn)
        return fallback if fallback.get('success') else result

    def _lookup_google(self, isbn: str) -> Dict:
        params = {'q': f'isbn:{isbn}'}
        api_key = os.environ.get('GOOGLE_API_KEY')
        if api_key:
            params['key'] = api_key

        try:
            response = requests.get(self.GOOGLE_BOOKS_API, params=params, timeout=10)
            # A key from a project without the Books API enabled gets 403 —
            # retry anonymously before giving up.
            if response.status_code in (400, 403) and api_key:
                response = requests.get(self.GOOGLE_BOOKS_API, params={'q': f'isbn:{isbn}'}, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('totalItems', 0) > 0 and 'items' in data:
                # Get the first match
                volume = data['items'][0].get('volumeInfo', {})

                # Map Google Books printType to eBay format
                print_type = volume.get('printType', '')
                format_map = {'BOOK': 'Paperback', 'MAGAZINE': 'Magazine'}
                book_format = format_map.get(print_type, 'Paperback')

                return {
                    'success': True,
                    'title': volume.get('title'),
                    'authors': volume.get('authors', []),
                    'publisher': volume.get('publisher'),
                    'publishedDate': volume.get('publishedDate'),
                    'description': volume.get('description'),
                    'pageCount': volume.get('pageCount'),
                    'categories': volume.get('categories', []),
                    'thumbnail': volume.get('imageLinks', {}).get('thumbnail'),
                    'language': volume.get('language', 'en'),
                    'format': book_format,
                    'isbn': isbn,
                    'source': 'google_books'
                }

            return {'success': False, 'error': 'Book not found'}

        except Exception as e:
            logger.error(f"[WARN] Google Books API failed: {e}")
            return {'success': False, 'error': str(e)}

    def _lookup_open_library(self, isbn: str) -> Dict:
        """Fallback metadata source. Slimmer data than Google Books, but keeps
        a scanning session alive through Google throttling."""
        try:
            response = requests.get(
                self.OPEN_LIBRARY_API,
                params={'bibkeys': f'ISBN:{isbn}', 'format': 'json', 'jscmd': 'data'},
                timeout=10,
            )
            response.raise_for_status()
            book = response.json().get(f'ISBN:{isbn}')
            if not book:
                return {'success': False, 'error': 'Book not found'}

            publishers = [p.get('name') for p in book.get('publishers', []) if p.get('name')]
            # Open Library dates look like "December 27, 2017" — downstream
            # slices [:4] for Publication Year, so normalize to the year.
            import re as _re
            year_match = _re.search(r'\b(1[5-9]\d{2}|20\d{2})\b', book.get('publish_date') or '')
            return {
                'success': True,
                'title': book.get('title'),
                'authors': [a.get('name') for a in book.get('authors', []) if a.get('name')],
                'publisher': publishers[0] if publishers else None,
                'publishedDate': year_match.group(1) if year_match else book.get('publish_date'),
                'description': '',
                'pageCount': book.get('number_of_pages'),
                'categories': [s.get('name') for s in book.get('subjects', [])[:5] if s.get('name')],
                'thumbnail': (book.get('cover') or {}).get('medium'),
                'language': 'en',
                'format': 'Paperback',
                'isbn': isbn,
                'source': 'open_library'
            }
        except Exception as e:
            logger.warning(f"Open Library fallback failed: {e}")
            return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    # Test
    svc = BookService()
    logger.info(svc.lookup_isbn("9780131103627"))  # C Programming Language
