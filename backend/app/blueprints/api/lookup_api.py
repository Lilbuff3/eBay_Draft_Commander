import html
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


@lookup_bp.route('/tools/research', methods=['GET'])
def search_prices():
    query = request.args.get('q')
    if not query: return error_response('Query required', 400)
    from backend.app.services.ebay.researcher import eBayResearcher
    researcher = eBayResearcher()
    result = researcher.search_sold(query)
    return jsonify(result)


# --- Template CRUD ---

def _template_to_response(template) -> dict:
    """Convert a ListingTemplate to the frontend Template shape."""
    data = template.data if isinstance(template.data, dict) else {}
    return {
        'id': template.name,
        'name': template.name,
        'category': data.get('category', 'General'),
        'description': data.get('description', ''),
        'fields': data.get('fields', {}),
        'isDefault': data.get('isDefault', False),
        'isFavorite': data.get('isFavorite', False),
        'usageCount': template.use_count,
    }


@lookup_bp.route('/tools/templates', methods=['GET'])
def list_templates():
    """List all templates."""
    try:
        from backend.app.services.template_manager import get_template_manager
        tm = get_template_manager()
        templates = tm.get_all()
        return jsonify([_template_to_response(t) for t in templates])
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return error_response(str(e))


@lookup_bp.route('/tools/templates', methods=['POST'])
def create_template():
    """Create or update a template."""
    data = request.json
    if not data:
        return error_response('Request body is required', 400)

    name = data.get('name')
    if not name:
        return error_response('Template name is required', 400)

    try:
        from backend.app.services.template_manager import get_template_manager
        tm = get_template_manager()

        # Store the frontend fields inside data_json
        template_data = {
            'category': data.get('category', 'General'),
            'description': data.get('description', ''),
            'fields': data.get('fields', {}),
            'isDefault': data.get('isDefault', False),
            'isFavorite': data.get('isFavorite', False),
        }

        saved = tm.save(name, template_data)
        return jsonify({'success': True, 'template': _template_to_response(saved)})
    except Exception as e:
        logger.error(f"Failed to create/update template: {e}")
        return error_response(str(e))


@lookup_bp.route('/tools/templates/<name>', methods=['PUT'])
def update_template(name):
    """Update an existing template by name."""
    data = request.json
    if not data:
        return error_response('Request body is required', 400)

    try:
        from backend.app.services.template_manager import get_template_manager
        tm = get_template_manager()

        existing = tm.get(name)
        if not existing:
            return error_response(f"Template '{name}' not found", 404)

        template_data = {
            'category': data.get('category', existing.data.get('category', 'General')),
            'description': data.get('description', existing.data.get('description', '')),
            'fields': data.get('fields', existing.data.get('fields', {})),
            'isDefault': data.get('isDefault', existing.data.get('isDefault', False)),
            'isFavorite': data.get('isFavorite', existing.data.get('isFavorite', False)),
        }

        saved = tm.save(name, template_data)
        return jsonify({'success': True, 'template': _template_to_response(saved)})
    except Exception as e:
        logger.error(f"Failed to update template '{name}': {e}")
        return error_response(str(e))


@lookup_bp.route('/tools/templates/<name>', methods=['DELETE'])
def delete_template(name):
    """Delete a template by name."""
    try:
        from backend.app.services.template_manager import get_template_manager
        tm = get_template_manager()

        if tm.delete(name):
            return jsonify({'success': True})
        else:
            return error_response(f"Template '{name}' not found", 404)
    except Exception as e:
        logger.error(f"Failed to delete template '{name}': {e}")
        return error_response(str(e))
