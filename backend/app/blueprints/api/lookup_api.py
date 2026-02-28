from flask import Blueprint, jsonify, request
from backend.app.blueprints.api.helpers import error_response
from backend.app.core.validator import validate_isbn
from backend.app.core.logger import get_logger

lookup_bp = Blueprint('lookup', __name__)
logger = get_logger('api.lookup')

@lookup_bp.route('/lookup/book', methods=['POST'])
def lookup_book_post():
    data = request.json
    isbn = data.get('isbn')
    if not isbn: return error_response('ISBN is required', 400)
    try:
        isbn = validate_isbn(isbn)
        from backend.app.services.book_service import BookService
        svc = BookService()
        result = svc.lookup_isbn(isbn)
        return jsonify(result)
    except Exception as e: return error_response(str(e))

@lookup_bp.route('/lookup/book', methods=['GET'])
def lookup_book():
    isbn = request.args.get('isbn')
    if not isbn: return error_response("ISBN is required", 400)
    isbn_clean = isbn.replace('-', '').strip()
    try:
        from backend.app.services.book_service import BookService
        book_service = BookService(); book_data = book_service.lookup_isbn(isbn_clean)
        if not book_data.get('success'): return error_response("Book not found", 404, book_data.get('error'))
        from backend.app.services.pricing_engine import PricingEngine
        pricing_engine = PricingEngine()
        title = book_data.get('title', ''); authors = ", ".join(book_data.get('authors', []))
        search_title = f"{title} {authors}"
        price_data = pricing_engine.get_price_with_comps(title=search_title, condition="Used - Good", isbn=isbn_clean)
        response = {
            "success": True, "title": f"{title} by {authors}",
            "item_specifics": {
                "Author": authors, "Publisher": book_data.get('publisher'),
                "Publication Year": book_data.get('publishedDate', '')[:4], "Book Title": title,
                "Language": "English", "Format": "Paperback", "ISBN": isbn_clean
            },
            "description": f"<h2>{title}</h2><p><b>Author:</b> {authors}<br><b>Publisher:</b> {book_data.get('publisher')}<br><b>Year:</b> {book_data.get('publishedDate')}</p><p>{book_data.get('description', '')}</p>",
            "category_id": "267", "price": price_data.get('suggested_price'), "pricing_data": price_data, "stock_photo": book_data.get('thumbnail')
        }
        return jsonify(response)
    except Exception as e: return error_response(str(e))

@lookup_bp.route('/lookup/category', methods=['GET'])
def lookup_category():
    """Search eBay category suggestions for a query string."""
    query = request.args.get('q')
    if not query:
        return error_response('Query is required', 400)
    try:
        from backend.app.services.ebay.taxonomy import get_category_suggestions
        results = get_category_suggestions(query)
        return jsonify(results)
    except Exception as e:
        return error_response(str(e))

@lookup_bp.route('/tools/research', methods=['GET'])
def search_prices():
    query = request.args.get('q')
    if not query: return error_response('Query required', 400)
    from backend.app.services.ebay.researcher import eBayResearcher
    researcher = eBayResearcher()
    result = researcher.search_sold(query)
    return jsonify(result)
