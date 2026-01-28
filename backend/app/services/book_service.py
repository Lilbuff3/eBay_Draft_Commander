
import requests
from typing import Dict, Optional

class BookService:
    """
    Fetches book metadata from Google Books API using ISBN.
    """
    
    GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
    
    def __init__(self):
        pass  # API Key not strictly valid for public access but recommended for higher limits
    
    def lookup_isbn(self, isbn: str) -> Dict:
        """
        Lookup book details by ISBN.
        
        Args:
            isbn: ISBN-10 or ISBN-13 string (digits only)
            
        Returns:
            Dict with title, authors, publisher, publishedDate, description, imageLinks
        """
        params = {
            'q': f'isbn:{isbn}'
        }
        
        try:
            response = requests.get(self.GOOGLE_BOOKS_API, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('totalItems', 0) > 0 and 'items' in data:
                # Get the first match
                volume = data['items'][0].get('volumeInfo', {})
                
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
                    'isbn': isbn,
                    'source': 'google_books'
                }
            
            return {'success': False, 'error': 'Book not found'}
            
        except Exception as e:
            print(f"⚠️ Google Books API failed: {e}")
            return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    # Test
    svc = BookService()
    print(svc.lookup_isbn("9780131103627"))  # C Programming Language
