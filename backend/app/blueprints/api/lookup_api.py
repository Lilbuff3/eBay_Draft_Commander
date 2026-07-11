import json
from flask import Blueprint, jsonify, request
from backend.app.blueprints.api.helpers import error_response
from backend.app.core.validator import validate_isbn
from backend.app.core.logger import get_logger
from backend.app.services.ebay.taxonomy import get_valid_condition_ids

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

@lookup_bp.route('/lookup/comps', methods=['GET'])
def lookup_comps():
    """Fast sourcing verdict: barcode (ISBN/UPC/EAN) -> comps + buy/pass. No AI, no metadata lookup."""
    import re
    raw = request.args.get('gtin', '')
    gtin = re.sub(r'[\s-]', '', raw).strip().upper()
    if not re.fullmatch(r'\d{8}|\d{9}[\dX]|\d{12,13}', gtin):
        return error_response('gtin must be an ISBN-10/13, UPC-A, or EAN-8/13', 400)
    # ISBN (books) = high-trust identifier; UPC/EAN (general merch) = looser.
    id_type = 'isbn' if re.fullmatch(r'\d{9}[\dX]|97[89]\d{10}', gtin) else 'upc'
    condition = request.args.get('condition') or 'USED_GOOD'
    try:
        from backend.app.services.pricing_engine import PricingEngine
        from backend.app.services.sourcing import compute_verdict, get_sourcing_settings

        knobs = get_sourcing_settings()
        engine = PricingEngine()
        comps = engine.search_sold_listings(gtin, limit=15, condition=condition)
        ebay_search_url = f"https://www.ebay.com/sch/i.html?_nkw={gtin}"

        if not comps:
            return jsonify({
                'success': True, 'gtin': gtin, 'id_type': id_type, 'verdict': 'NO_DATA', 'comp_count': 0,
                'max_buy': None, 'est_sold_value': None, 'net_proceeds': None,
                'would_list_at': None, 'median_price': None, 'price_range': None,
                'confidence': None, 'confidence_reason': 'No comparable listings found',
                'comps': [], 'reasoning': 'No comparable listings found',
                'ebay_search_url': ebay_search_url,
            })

        price_data = engine.calculate_suggested_price(
            comps, our_condition=condition,
            shipping_cost=knobs['ship_cost'], availability=None)
        verdict = compute_verdict(
            price_data.get('median_price'), price_data.get('comp_count', 0),
            [c.get('price') for c in comps],
            min_profit=knobs['min_profit'], roi_multiple=knobs['roi_multiple'],
            ship_cost=knobs['ship_cost'], id_type=id_type)

        return jsonify({
            'success': True, 'gtin': gtin, 'id_type': id_type,
            'verdict': verdict['verdict'], 'max_buy': verdict['max_buy'],
            'est_sold_value': verdict['est_sold_value'], 'net_proceeds': verdict['net_proceeds'],
            'would_list_at': price_data.get('suggested_price'),
            'median_price': price_data.get('median_price'),
            'comp_count': price_data.get('comp_count', 0),
            'price_range': verdict['price_range'],
            'confidence': verdict['confidence'], 'confidence_reason': verdict['confidence_reason'],
            'comps': comps[:5],
            'reasoning': price_data.get('reasoning'),
            'ebay_search_url': ebay_search_url,
        })
    except Exception as e:
        logger.error(f"Sourcing comps lookup failed for {gtin}: {e}")
        return error_response(str(e))


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

@lookup_bp.route('/lookup/category/<category_id>/aspects', methods=['GET'])
def category_aspects(category_id):
    """Fetch formatted eBay required/optional aspects for a given category ID."""
    if not category_id:
        return error_response('Category ID is required', 400)
    try:
        from backend.app.services.ebay.taxonomy import get_item_aspects
        aspects = get_item_aspects(category_id)
        
        required_aspects = aspects.get('required', [])
        optional_aspects = aspects.get('optional', [])

        for aspect in required_aspects:
            aspect['isRequired'] = True
            if 'values' in aspect:
                aspect['values'] = aspect['values'][:50]

        for aspect in optional_aspects:
            aspect['isRequired'] = False
            if 'values' in aspect:
                aspect['values'] = aspect['values'][:50]

        full_schema = required_aspects + optional_aspects
        return jsonify(full_schema)
    except Exception as e:
        return error_response(str(e))

@lookup_bp.route('/lookup/category/<category_id>/conditions', methods=['GET'])
def get_valid_conditions(category_id):
    """Return valid eBay condition IDs and labels for a category."""
    from backend.app.core.constants import CONDITION_ID_MAP

    valid_ids = get_valid_condition_ids(category_id)
    # Build reverse map: condition_id -> display label
    id_to_label = {}
    for enum_key, cid in CONDITION_ID_MAP.items():
        display = enum_key.replace('_', ' ').title()
        id_to_label.setdefault(str(cid), display)

    conditions = [{'id': cid, 'label': id_to_label.get(cid, f'Condition {cid}')} for cid in valid_ids]
    return jsonify({'category_id': category_id, 'condition_ids': valid_ids, 'conditions': conditions})
